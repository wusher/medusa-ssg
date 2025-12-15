import asyncio
from pathlib import Path

import pytest

from medusa.server import DevServer, _ChangeHandler, _ReloadHandler


class DummyEvent:
    def __init__(self, path, is_directory=False):
        self.src_path = path
        self.is_directory = is_directory


def test_change_handler_skips_output(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    server.output_dir = tmp_path / "output"
    server.output_dir.mkdir()

    called = {}

    def fake_rebuild(include_drafts):
        called["drafts"] = include_drafts

    server.rebuild = fake_rebuild
    handler = _ChangeHandler(server, include_drafts=True)

    handler.on_any_event(DummyEvent(str(server.output_dir / "index.html")))
    assert not called

    handler.on_any_event(DummyEvent(str(tmp_path / "site" / "index.md")))
    assert called["drafts"] is True


def test_async_broadcast_tracks_stale_clients():
    server = DevServer(Path("."))

    class GoodWS:
        def __init__(self):
            self.messages = []

        async def send(self, msg):
            self.messages.append(msg)

    class BadWS:
        async def send(self, msg):
            raise RuntimeError("fail")

    good = GoodWS()
    bad = BadWS()
    server._ws_clients = {good, bad}
    asyncio.run(server._async_broadcast("hello"))
    assert good.messages == ["hello"]
    assert bad not in server._ws_clients


def test_broadcast_reload_invokes_runner(monkeypatch):
    server = DevServer(Path("."))
    called = {}

    def fake_runner(coro, loop):
        called["ran"] = True
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    monkeypatch.setattr("medusa.server.asyncio.run_coroutine_threadsafe", fake_runner)
    server._broadcast_reload()
    assert called["ran"]


def test_reload_handler_injects_script(tmp_path):
    html = tmp_path / "index.html"
    html.write_text("<html><body>Hello</body></html>", encoding="utf-8")

    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/index.html"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler.wfile = tmp_path.joinpath("out.bin").open("wb")
    handler._headers_buffer = []

    def send_header(key, value):
        handler._headers_buffer.append(f"{key}: {value}\r\n".encode())

    handler.send_header = send_header
    handler.send_response = lambda code, message=None: None

    _ReloadHandler.end_headers(handler)
    result = _ReloadHandler.send_head(handler)
    handler.wfile.close()
    output = tmp_path.joinpath("out.bin").read_bytes()
    assert result is None
    assert b"reload" in output


def test_stop_and_ws_handler(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    server._observer = None
    server.stop()

    class DummyObserver:
        def __init__(self):
            self.calls = []

        def stop(self):
            self.calls.append("stop")

        def join(self):
            self.calls.append("join")

    server._observer = DummyObserver()
    server.stop()
    assert server._observer.calls == ["stop", "join"]

    class DummyWS:
        def __init__(self):
            self.closed = False

        async def wait_closed(self):
            self.closed = True

    ws = DummyWS()
    asyncio.run(server._ws_handler(ws))
    assert ws.closed
    assert ws not in server._ws_clients


def test_start_watcher_and_rebuild(monkeypatch, tmp_path):
    (tmp_path / "site").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "data").mkdir()
    server = DevServer(tmp_path)

    scheduled = []

    class DummyObserver:
        def schedule(self, handler, path, recursive):
            scheduled.append((path, recursive))

        def start(self):
            scheduled.append(("started", True))

        def stop(self):
            scheduled.append(("stopped", False))

        def join(self):
            scheduled.append(("joined", False))

    monkeypatch.setattr("medusa.server.Observer", DummyObserver)
    server._start_watcher(include_drafts=False)
    assert any("site" in path for path, _ in scheduled if isinstance(path, str))

    calls = []
    monkeypatch.setattr("medusa.server.build_site", lambda root, include_drafts=False: calls.append(include_drafts))
    server._broadcast_reload = lambda: calls.append("reloaded")
    server.rebuild(include_drafts=True)
    assert calls == [True, "reloaded"]


def test_reload_handler_without_body(tmp_path):
    html = tmp_path / "plain.html"
    html.write_text("<html>No body here</html>", encoding="utf-8")
    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/plain.html"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.wfile = tmp_path.joinpath("out2.bin").open("wb")
    handler.send_response = lambda code, message=None: None
    handler.send_header = lambda *args, **kwargs: None
    _ReloadHandler.send_head(handler)
    handler.wfile.close()
    assert b"reload" in tmp_path.joinpath("out2.bin").read_bytes()


def test_change_handler_directory_event():
    server = DevServer(Path("."))
    handler = _ChangeHandler(server, include_drafts=False)
    # should return early without error
    handler.on_any_event(DummyEvent("ignored", is_directory=True))


def test_start_watcher_without_paths(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    scheduled = []

    class DummyObserver:
        def schedule(self, handler, path, recursive):
            scheduled.append(("schedule", path, recursive))

        def start(self):
            scheduled.append(("start", True, True))

    monkeypatch.setattr("medusa.server.Observer", DummyObserver)
    server._start_watcher(include_drafts=False)
    assert ("schedule", str(tmp_path), False) in scheduled
    assert ("start", True, True) in scheduled


def test_send_head_falls_back(tmp_path):
    css = tmp_path / "style.css"
    css.write_text("body{}", encoding="utf-8")
    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/style.css"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    in_file = tmp_path.joinpath("in.bin")
    in_file.write_bytes(b"")
    handler.rfile = in_file.open("rb")
    handler.wfile = tmp_path.joinpath("out3.bin").open("wb")
    handler.headers = {}
    handler.send_response = lambda code, message=None: None
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None
    result = _ReloadHandler.send_head(handler)
    handler.wfile.close()
    assert result is not None
