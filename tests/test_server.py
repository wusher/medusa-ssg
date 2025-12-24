import asyncio
import io
from pathlib import Path

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


def test_dev_server_port_override(tmp_path):
    server = DevServer(tmp_path, http_port=5055, ws_port=None)
    assert server.http_port == 5055
    assert server.ws_port == 5056

    explicit = DevServer(tmp_path, http_port=5055, ws_port=6000)
    assert explicit.ws_port == 6000
    assert f":{explicit.ws_port}" in explicit._reload_script


def test_rebuild_waits_before_reload(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    server._post_build_delay = 0.01
    calls = []

    def fake_build(*args, **kwargs):
        calls.append(("build", kwargs.get("output_dir_override")))

    monkeypatch.setattr("medusa.server.build_site", fake_build)
    monkeypatch.setattr(
        "medusa.server.DevServer._broadcast_reload",
        lambda self=server: calls.append("reload"),
    )
    slept = []
    monkeypatch.setattr("medusa.server.time.sleep", lambda secs: slept.append(secs))

    server.rebuild(include_drafts=False)
    assert len(calls) == 2
    assert calls[0][0] == "build"
    assert calls[0][1] == server._staging_dir
    assert calls[1] == "reload"
    assert slept == [0.01]


def test_rebuild_avoids_cleaning_output(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    server._post_build_delay = 0
    server._broadcast_reload = lambda: None
    server._compute_signature = lambda: ("sig",)
    called = {}

    def fake_build(
        root,
        include_drafts=False,
        root_url=None,
        clean_output=True,
        output_dir_override=None,
    ):
        called["clean_output"] = clean_output
        called["output_dir_override"] = output_dir_override
        # simulate writing into staging
        (output_dir_override / "index.html").write_text("new", encoding="utf-8")

    monkeypatch.setattr("medusa.server.build_site", fake_build)
    server.rebuild(include_drafts=False)
    assert called["clean_output"] is True
    assert called["output_dir_override"] == server._staging_dir
    assert server.output_dir.joinpath("index.html").read_text(encoding="utf-8") == "new"
    assert not server._staging_dir.exists()


def test_rebuild_guard(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    calls = []
    monkeypatch.setattr(
        "medusa.server.build_site", lambda *args, **kwargs: calls.append("built")
    )
    server._broadcast_reload = lambda: calls.append("reloaded")
    server._debounce_seconds = 0.0

    sigs = [("a",), ("a",), ("b",)]

    def fake_sig():
        return sigs.pop(0) if sigs else ("b",)

    server._compute_signature = fake_sig
    server.rebuild(include_drafts=False)
    server._rebuilding = True
    server.rebuild(include_drafts=False)  # skipped due to rebuilding flag
    server._rebuilding = False
    server.rebuild(include_drafts=False)  # skipped due to same signature
    server.rebuild(include_drafts=False)  # signature changed -> rebuild
    assert calls == ["built", "reloaded", "built", "reloaded"]


def test_compute_signature_handles_missing(monkeypatch, tmp_path):
    server = DevServer(tmp_path)
    (tmp_path / "site").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "site" / "nested").mkdir()
    (tmp_path / "site" / "index.md").write_text("hi", encoding="utf-8")
    (tmp_path / "assets" / "main.js").write_text("js", encoding="utf-8")
    (tmp_path / "data" / "site.yaml").write_text("title: t", encoding="utf-8")
    broken = tmp_path / "assets" / "missing.txt"
    broken.symlink_to(tmp_path / "nope.txt")

    sig = server._compute_signature()
    assert sig is not None
    assert any("site/index.md" in entry[0] for entry in sig)


def test_compute_signature_empty(tmp_path):
    server = DevServer(tmp_path)
    assert server._compute_signature() is None


def test_change_handler_skips_node_modules(tmp_path):
    server = DevServer(tmp_path)
    handler = _ChangeHandler(server, include_drafts=False)

    class DummyEvent:
        def __init__(self, path, is_dir=False):
            self.src_path = path
            self.is_directory = is_dir

    # Should be skipped
    handler.on_any_event(DummyEvent(str(tmp_path / "node_modules" / "file.txt")))
    # Non-output should trigger rebuild
    called = {}

    def fake_rebuild(include_drafts):
        called["hit"] = True

    server.rebuild = fake_rebuild
    handler.on_any_event(DummyEvent(str(tmp_path / "site" / "file.txt")))
    assert called["hit"]


def test_ws_start_failure(monkeypatch, tmp_path, capsys):
    server = DevServer(tmp_path, http_port=5055, ws_port=5057)

    async def fake_run():
        raise OSError("bind error")

    monkeypatch.setattr(server, "_run_ws_server", fake_run)
    server._loop = asyncio.new_event_loop()
    server._start_ws()
    out = capsys.readouterr().out
    assert "failed to start" in out


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
    monkeypatch.setattr(
        "medusa.server.build_site",
        lambda root, include_drafts=False, **kwargs: calls.append(include_drafts),
    )
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


def test_serve_404_uses_custom_page(tmp_path):
    error_page = tmp_path / "404.html"
    error_page.write_text("<html><body>oops</body></html>", encoding="utf-8")

    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/missing"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler.wfile = io.BytesIO()

    codes = []
    handler.send_response = lambda code, message=None: codes.append(code)
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None
    handler.send_error = lambda *args, **kwargs: codes.append("error")

    result = _ReloadHandler._serve_404(handler)
    assert result is None
    assert codes == [404]
    body = handler.wfile.getvalue().decode()
    assert "oops" in body
    assert "reload" in body


def test_send_head_serves_directory_index(tmp_path):
    posts = tmp_path / "posts"
    posts.mkdir()
    (posts / "index.html").write_text(
        "<html><body>index</body></html>", encoding="utf-8"
    )

    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/posts/"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler.wfile = io.BytesIO()

    codes = []
    handler.send_response = lambda code, message=None: codes.append(code)
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None

    result = _ReloadHandler.send_head(handler)
    assert result is None
    assert codes == [200]
    assert b"reload" in handler.wfile.getvalue()


def test_serve_404_without_body_tag(tmp_path):
    error_page = tmp_path / "404.html"
    error_page.write_text("<html>no body tag</html>", encoding="utf-8")

    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/missing"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler.wfile = io.BytesIO()

    handler.send_response = lambda *args, **kwargs: None
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None
    handler.send_error = lambda *args, **kwargs: None

    _ReloadHandler._serve_404(handler)
    body = handler.wfile.getvalue().decode()
    assert "reload" in body


def test_send_head_missing_file_triggers_404(tmp_path):
    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/missing.html"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler.wfile = io.BytesIO()

    called = {}
    handler.send_response = lambda *args, **kwargs: called.setdefault(
        "resp", []
    ).append(args[0])
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None

    def send_error(code, message=None):
        called["error"] = code

    handler.send_error = send_error
    result = _ReloadHandler.send_head(handler)
    assert result is None
    assert called["error"] == 404


def test_directory_without_index_returns_404(tmp_path):
    posts = tmp_path / "posts"
    posts.mkdir()
    (posts / "note.txt").write_text("hi", encoding="utf-8")

    handler = _ReloadHandler.__new__(_ReloadHandler)
    handler.path = "/posts/"
    handler.directory = str(tmp_path)
    handler.command = "GET"
    handler.request_version = "HTTP/1.1"
    handler.server_version = ""
    handler.sys_version = ""
    handler._headers_buffer = []
    handler.headers = {}
    handler.rfile = io.BytesIO(b"")
    handler.wfile = io.BytesIO()

    called = {}

    def fake_send_error(code, message=None):
        called["error"] = code

    handler.send_response = lambda code, message=None: called.setdefault(
        "responses", []
    ).append(code)
    handler.send_header = lambda *args, **kwargs: None
    handler.end_headers = lambda: None
    handler.send_error = fake_send_error

    result = _ReloadHandler.send_head(handler)
    assert called["error"] == 404
    assert result is None


def test_prepare_staging_dir_removes_existing(tmp_path):
    """Test that _prepare_staging_dir removes existing staging directory."""
    server = DevServer(tmp_path)

    # Pre-create staging directory with content
    staging = server._staging_dir
    staging.mkdir(parents=True)
    (staging / "old_file.html").write_text("old content", encoding="utf-8")
    assert staging.exists()
    assert (staging / "old_file.html").exists()

    # Call _prepare_staging_dir
    result = server._prepare_staging_dir()

    # Staging should be recreated (empty)
    assert result == staging
    assert staging.exists()
    assert not (staging / "old_file.html").exists()


def test_change_handler_with_none_staging_dir(tmp_path):
    """Test _ChangeHandler handles case where _staging_dir is None."""
    server = DevServer(tmp_path)
    server._staging_dir = None  # Set to None to hit the branch

    called = {}

    def fake_rebuild(include_drafts):
        called["hit"] = True

    server.rebuild = fake_rebuild
    handler = _ChangeHandler(server, include_drafts=False)

    # Should still work and call rebuild
    handler.on_any_event(DummyEvent(str(tmp_path / "site" / "index.md")))
    assert called.get("hit") is True
