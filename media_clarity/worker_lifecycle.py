"""Contain the subtitle compute process and its decoders, without model imports."""
import ctypes
import os
import signal
import subprocess
import sys
import threading


class WindowsJob:
    """A noninheritable kill-on-close job, assigned before the compute handshake."""
    def __init__(self, process):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('user_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', w.DWORD), ('minimum', ctypes.c_size_t),
                        ('maximum', ctypes.c_size_t), ('active', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            'SetInformationJobObject': ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
            'CloseHandle': ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name); function.argtypes = args; function.restype = result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError('worker containment unavailable')
        try:
            limits = Extended(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise OSError('worker containment unavailable')
            # CPython Popen owns this live process handle; avoid opening a recycled PID.
            if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
                raise OSError('worker containment unavailable')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def parent_gone():
    # This thread belongs to the lightweight guardian, never the model's GIL.
    os.read(sys.stdin.fileno(), 1)
    if os.name != 'nt':
        os.killpg(os.getpid(), signal.SIGKILL)
    os._exit(1)  # Windows closes the guardian's noninheritable Job handle.


def supervise(command):
    if os.name != 'nt' and os.getpgrp() != os.getpid():
        raise OSError('worker containment unavailable')
    threading.Thread(target=parent_gone, daemon=True).start()
    child = subprocess.Popen(command, stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    job = None
    try:
        if os.name == 'nt':
            job = WindowsJob(child)
        # A compute child cannot import models or launch FFmpeg before containment.
        child.stdin.write(b'1'); child.stdin.close()
        code = child.wait()
        if code and os.name != 'nt':
            os.killpg(os.getpid(), signal.SIGKILL)
        return code
    finally:
        if job:
            job.close()
        if child.poll() is None:
            if os.name != 'nt':
                os.killpg(os.getpid(), signal.SIGKILL)
            child.kill()
            child.wait(timeout=5)
        if not child.stdin.closed:
            child.stdin.close()
