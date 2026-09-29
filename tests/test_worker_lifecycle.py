"""Actual paced FFmpeg descendants stop on pause or parent EOF; no model/API."""
import ctypes
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from media_clarity.jobs import Jobs, worker_guard
from media_clarity.storage import MediaError


def running(pid):
    if os.name == 'nt':
        from ctypes import wintypes as w
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; api.OpenProcess.restype = w.HANDLE
        api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; api.WaitForSingleObject.restype = w.DWORD
        api.CloseHandle.argtypes = [w.HANDLE]; api.CloseHandle.restype = w.BOOL
        handle = api.OpenProcess(0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return False
            raise OSError('cannot inspect owned fixture process')
        try:
            result = api.WaitForSingleObject(handle, 0)
            if result not in (0, 258):
                raise OSError('cannot inspect owned fixture process')
            return result == 258
        finally:
            api.CloseHandle(handle)
    try:
        if os.waitpid(pid, os.WNOHANG)[0] == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


COMPUTE = r'''
import ctypes, os, sys
from pathlib import Path
if os.read(sys.stdin.fileno(), 1) != b'1':
    sys.exit(1)
from media_clarity import qwen
from media_clarity.jobs import worker_guard
root = Path(sys.argv[1])
original_run, original_popen = qwen.subprocess.run, qwen.subprocess.Popen
class Observed(original_popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        (root/'decoder.pid').write_text(str(self.pid))
        if sys.argv[2] == 'gil':
            (ctypes.PyDLL('kernel32').Sleep(30000) if os.name == 'nt'
             else ctypes.PyDLL(None).sleep(30))
qwen.subprocess.Popen = Observed
def paced(args, **kwargs):
    args = list(args); args.insert(args.index('-i'), '-re')
    return original_run(args, **kwargs)
qwen.subprocess.run = paced
with worker_guard(root), qwen.decoded_audio(root/'source.m4a', 30, 0):
    pass
'''


@unittest.skipUnless(os.name == 'nt' or sys.platform == 'linux', 'process inspection requires Windows or Linux')
class WorkerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == 'linux' and ctypes.CDLL(None).prctl(36, 1, 0, 0, 0):
            raise OSError('fixture cannot reap its stopped descendants')

    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source.m4a'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:sample_rate=16000:duration=30',
                            '-c:a', 'aac', str(source)], check=True, capture_output=True, timeout=10)
            original = hashlib.sha256(source.read_bytes()).hexdigest()
            (root/'compute.py').write_text(COMPUTE)
            guardian_code = '''from media_clarity import worker_lifecycle as lifecycle
import sys
from pathlib import Path
original = lifecycle.subprocess.Popen
class Observed(original):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        (Path(sys.argv[3])/'compute.pid').write_text(str(self.pid))
lifecycle.subprocess.Popen = Observed
sys.exit(lifecycle.supervise(sys.argv[1:]))'''
            child = subprocess.Popen([sys.executable, '-c', guardian_code, sys.executable,
                                      str(root/'compute.py'), str(root), mode],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=os.name != 'nt',
                                     env={**os.environ, 'PYTHONPATH':str(Path.cwd()),
                                          'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
            pids = []
            try:
                deadline = time.monotonic()+8
                while not (root/'decoder.pid').exists() and time.monotonic() < deadline:
                    if child.poll() is not None:
                        self.fail('guardian stopped before decoder: '+child.stderr.read().decode())
                    time.sleep(.02)
                self.assertTrue((root/'decoder.pid').exists(), 'decoder did not start')
                pids = [int((root/name).read_text()) for name in ('compute.pid','decoder.pid')]
                self.assertTrue(all(running(pid) for pid in pids))
                # Let the paced decoder make real output before requesting shutdown.
                time.sleep(.2)
                before = time.monotonic()
                if mode == 'pause':
                    jobs = object.__new__(Jobs); jobs.process = child; jobs._terminate()
                else:
                    child.stdin.close()  # The exact EOF produced by server death.
                    child.wait(timeout=5)
                deadline = time.monotonic()+3
                released = False
                while time.monotonic() < deadline:
                    if all(not running(pid) for pid in pids):
                        try:
                            # A signaled Windows process can still be releasing
                            # file handles. Observe the actual lease in the same
                            # bounded shutdown window, not just process state.
                            with worker_guard(root):
                                pass
                        except MediaError as error:
                            if error.code != 'processing_worker_active':
                                raise
                        else:
                            released = True
                            break
                    time.sleep(.02)
                self.assertTrue(all(not running(pid) for pid in pids), 'owned compute/FFmpeg survived')
                self.assertTrue(released, 'owned worker lease was not released')
                self.assertLess(time.monotonic()-before, 8)
                self.assertFalse(list(root.glob('qwen-audio-*')))
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original)
            finally:
                if child.poll() is None:
                    if os.name == 'nt':child.kill()
                    else:os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)
                for pid in pids:
                    if running(pid):
                        os.kill(pid, signal.SIGTERM if os.name == 'nt' else signal.SIGKILL)
                for stream in (child.stdin, child.stdout, child.stderr):
                    if not stream.closed:stream.close()

    def test_pause_stops_actual_compute_and_decoder(self):
        self.exercise('pause')

    def test_parent_eof_stops_actual_compute_and_decoder(self):
        self.exercise('eof')

    def test_parent_eof_stops_decoder_when_compute_holds_gil(self):
        self.exercise('gil')
