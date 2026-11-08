#!/usr/bin/env python3
"""Start the local HTTP API and Nick's Next.js interface; Ctrl-C stops both."""
from pathlib import Path
import argparse
import errno
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def occupied_ports(ports):
    """Check both ports before starting either service or opening its database."""
    occupied = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            # Match the servers' reuse behavior: recently closed connections in
            # TIME_WAIT must not prevent an immediate, otherwise valid restart.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                occupied.append(port)
    return occupied


def paper_api_ready(url):
    try:
        # Local checks must not go through a configured external HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=1) as response:
            data = json.load(response)
        return data.get('ok') is True and data.get('trading_mode') == 'paper_only'
    except (OSError, ValueError, urllib.error.URLError):
        return False


def wait_until_ready(child, url, stopping, timeout=45):
    deadline = time.monotonic() + timeout
    while not stopping() and child.poll() is None:
        if paper_api_ready(url):
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(.2)
    return False


def shutdown(children):
    # npm can exit before its Next.js child. Terminate our process groups even
    # when the immediate child has exited, so no server is left holding a port.
    for child in reversed(children):
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', action='store_true', help='Use the prebuilt Next production app')
    args = parser.parse_args()
    python = ROOT / '.venv' / 'bin' / 'python'
    if not python.exists() or not (ROOT/'app/node_modules').exists():
        sys.exit('Install dependencies first. See README.md. Expected .venv and app/node_modules.')
    npm = shutil.which('npm')
    if not npm:
        sys.exit('Node.js and npm are required.')
    try:
        backend_port = int(os.getenv('BACKEND_PORT', '8000'))
        frontend_port = int(os.getenv('FRONTEND_PORT', '3000'))
        if not all(1 <= p <= 65535 for p in (backend_port, frontend_port)) or backend_port == frontend_port:
            raise ValueError()
    except ValueError:
        parser.error('FRONTEND_PORT and BACKEND_PORT must be different integers between 1 and 65535.')
    occupied = occupied_ports((frontend_port, backend_port))
    if occupied:
        ports = ', '.join(map(str, occupied))
        print(f'Cannot start: local port(s) {ports} already in use. No new services were started.', file=sys.stderr)
        print(f'If Pub Hedge is already running, open http://localhost:{frontend_port}.', file=sys.stderr)
        print('To restart it in this terminal, stop the existing instance with Ctrl-C in its terminal first.', file=sys.stderr)
        return 1
    env = {**os.environ, 'BACKEND_URL': f'http://127.0.0.1:{backend_port}', 'NEXT_TELEMETRY_DISABLED':'1'}
    children = []
    stop_requested = False
    def stop(*_):
        nonlocal stop_requested
        stop_requested = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        print('Starting Pub Hedge locally…', flush=True)
        children.append(subprocess.Popen([str(python),'-m','uvicorn','src.api:app','--host','127.0.0.1','--port',str(backend_port)], cwd=ROOT, env=env, start_new_session=True))
        if not wait_until_ready(children[0], f'http://127.0.0.1:{backend_port}/api/health', lambda: stop_requested):
            if not stop_requested:
                print('The API failed to become ready. Check the error above.', file=sys.stderr)
            return 0 if stop_requested else 1
        children.append(subprocess.Popen([npm,'run','start' if args.production else 'dev','--','--hostname','127.0.0.1','--port',str(frontend_port)], cwd=ROOT/'app', env=env, start_new_session=True))
        if not wait_until_ready(children[1], f'http://127.0.0.1:{frontend_port}/api/health', lambda: stop_requested):
            if not stop_requested:
                print('The frontend failed to become ready. Check the error above.', file=sys.stderr)
            return 0 if stop_requested else 1
        print(f'\nPub Hedge: http://localhost:{frontend_port}\nAPI: http://127.0.0.1:{backend_port}/docs\nPaper simulation only. Ctrl-C stops both services.\n', flush=True)
        while not stop_requested and all(p.poll() is None for p in children):
            time.sleep(.5)
        if not stop_requested:
            print('A service stopped unexpectedly; stopping the other service.', file=sys.stderr)
            return 1
        return 0
    finally:
        shutdown(children)


if __name__ == '__main__':
    raise SystemExit(main())
