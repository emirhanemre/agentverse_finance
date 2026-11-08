"""Process-lifecycle regressions for the one-command local launcher."""
from unittest.mock import Mock

import pytest

from scripts import start


@pytest.mark.parametrize('occupied', [[3000], [8000], [3000, 8000]])
def test_occupied_port_starts_neither_service(tmp_path, monkeypatch, capsys, occupied):
    (tmp_path / '.venv/bin').mkdir(parents=True)
    (tmp_path / '.venv/bin/python').touch()
    (tmp_path / 'app/node_modules').mkdir(parents=True)
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start.shutil, 'which', lambda _: 'npm')
    monkeypatch.setattr(start, 'occupied_ports', lambda _: occupied)
    spawn = Mock()
    monkeypatch.setattr(start.subprocess, 'Popen', spawn)
    monkeypatch.setattr(start.sys, 'argv', ['start.py'])
    monkeypatch.delenv('FRONTEND_PORT', raising=False)
    monkeypatch.delenv('BACKEND_PORT', raising=False)
    assert start.main() == 1
    spawn.assert_not_called()
    assert 'No new services were started' in capsys.readouterr().err


def test_cleanup_stops_descendants_even_when_npm_has_exited(monkeypatch):
    child = Mock(pid=12345)
    child.poll.return_value = 0
    kill = Mock()
    monkeypatch.setattr(start.os, 'killpg', kill)
    start.shutdown([child])
    kill.assert_called_once_with(12345, start.signal.SIGTERM)
    child.wait.assert_called_once_with(timeout=5)


def test_exited_child_cannot_be_reported_ready(monkeypatch):
    child = Mock()
    child.poll.return_value = 1
    ready = Mock(return_value=True)
    monkeypatch.setattr(start, 'paper_api_ready', ready)
    assert not start.wait_until_ready(child, 'http://127.0.0.1/api/health', lambda: False)
    ready.assert_not_called()
