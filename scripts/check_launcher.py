"""Exercise real startup, duplicate launch, health and clean shutdown locally.

Requires the production frontend build. Uses an isolated temporary database and
leaves both default ports free on completion. Never kills an existing service.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import time

from scripts.start import occupied_ports, paper_api_ready

ROOT = Path(__file__).resolve().parent.parent


if __name__ == '__main__':
    assert not occupied_ports((3000, 8000)), 'Stop existing services before running this isolated check.'
    with tempfile.TemporaryDirectory(prefix='pub-hedge-launcher-') as directory:
        log = Path(directory) / 'launcher.log'
        env = {**os.environ, 'APP_DB_PATH': str(Path(directory) / 'check.db'), 'FRONTEND_PORT':'3000', 'BACKEND_PORT':'8000'}
        with log.open('w') as output:
            process = subprocess.Popen([sys.executable, 'scripts/start.py', '--production'], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 60
            while not paper_api_ready('http://127.0.0.1:3000/api/health'):
                assert process.poll() is None, log.read_text()
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(.2)
            duplicate = subprocess.run([sys.executable,'scripts/start.py','--production'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
            assert duplicate.returncode == 1, duplicate.stdout + duplicate.stderr
            assert 'No new services were started' in duplicate.stderr
            assert 'Started server process' not in duplicate.stderr
            assert paper_api_ready('http://127.0.0.1:8000/api/health')
            assert paper_api_ready('http://127.0.0.1:3000/api/health')
            print('Startup and duplicate-launch checks passed.')
        finally:
            process.terminate()
            process.wait(timeout=15)
        assert process.returncode == 0, log.read_text()
        deadline = time.monotonic() + 5
        while occupied_ports((3000,8000)) and time.monotonic() < deadline:
            time.sleep(.1)
        assert not occupied_ports((3000,8000)), log.read_text()
        print('Clean shutdown passed. Ports 3000 and 8000 are free.')
