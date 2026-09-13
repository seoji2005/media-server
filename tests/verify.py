"""The same model-free product checks locally and in CI; missing tools fail."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
commands = [
    [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
    [shutil.which('npm.cmd' if os.name == 'nt' else 'npm'), 'test', '--prefix', 'tests/ui'],
    [sys.executable, 'tests/browser_smoke.py'],
    [sys.executable, 'tests/codespaces_smoke.py', '--browser'],
]
if not commands[1][0]:
    sys.exit('Node.js/npm required: install dependencies with npm ci --prefix tests/ui')
for command in commands:
    result = subprocess.run(command, cwd=root)
    if result.returncode:
        sys.exit(result.returncode)
print('PASS: Python, all DOM suites, real browser playback and server restart')
