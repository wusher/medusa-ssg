"""Development server for Medusa.

Serves the built site with live reload and sane defaults for local authoring:
- Injects a reload script into HTML responses.
- Rejects directory listings and missing paths with a 404 (serving 404.html when present).
- Watches source folders and triggers rebuilds plus client reloads.

Key classes:
- DevServer: Main class for running the development server.
- _ReloadHandler: HTTP request handler that injects reload script and enforces 404s.
- _ChangeHandler: File system event handler for triggering rebuilds.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import shutil
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import websockets
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .build import build_site, load_config


class _ReloadHandler(SimpleHTTPRequestHandler):
    """HTTP request handler that injects live reload script into HTML pages.

    Attributes:
        reload_script: JavaScript code for WebSocket connection to trigger reloads.
    """

    reload_script_template = """
    <script>
    (() => {{
      const ws = new WebSocket('ws://' + location.hostname + ':{ws_port}');
      ws.onmessage = (event) => {{
        const data = JSON.parse(event.data || '{{}}');
        if (data.type === 'reload') location.reload();
      }};
    }})();
    </script>
    """
    reload_script = reload_script_template.format(ws_port=4001)

    def end_headers(self):
        # Ensure CORS for dev
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def list_directory(self, path):  # pragma: no cover - exercised via send_head
        # Never expose directory listings; treat as missing content.
        return self._serve_404()

    def _serve_404(self):
        """Serve 404.html (when present) with injected reload script and a 404 status."""
        error_page = Path(self.directory) / "404.html"
        if error_page.exists():
            content = error_page.read_text(encoding="utf-8")
            if "</body>" in content:
                content = content.replace("</body>", f"{self.reload_script}</body>")
            else:
                content += self.reload_script
            encoded = content.encode("utf-8")
            self.send_response(404)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return None
        self.send_error(404, "File not found")
        return None

    def send_head(self):
        path = self.translate_path(self.path)
        # Check if path exists (file or directory with index.html)
        path_obj = Path(path)
        if path_obj.is_dir():
            index_path = path_obj / "index.html"
            if index_path.exists():
                path = str(index_path)
                path_obj = index_path
            else:
                return self._serve_404()
        elif not path_obj.exists():
            return self._serve_404()

        if path.endswith(".html"):
            content = path_obj.read_text(encoding="utf-8")
            if "</body>" in content:
                content = content.replace("</body>", f"{self.reload_script}</body>")
            else:
                content += self.reload_script
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return None
        return super().send_head()


class DevServer:
    """Development server with live reload functionality.

    Attributes:
        project_root: Root directory of the project.
        config: Site configuration.
        output_dir: Directory where built site is served.
        ws_port: Port for WebSocket connections.
        http_port: Port for HTTP server.
        _observer: File system observer for changes.
        _ws_clients: Set of connected WebSocket clients.
        _loop: Event loop for WebSocket handling.
    """

    def __init__(self, project_root: Path, http_port: int | None = None, ws_port: int | None = None):
        """Initialize the development server.

        Args:
            project_root: Root directory of the project.
            http_port: Optional override for HTTP port.
        """
        self.project_root = project_root
        self.config = load_config(project_root)
        self.output_dir = project_root / self.config.get("output_dir", "output")
        self._staging_dir = self.output_dir.with_suffix(self.output_dir.suffix + ".staging")
        base_http = int(http_port or self.config.get("port", 4000))
        resolved_ws = (
            ws_port
            if ws_port is not None
            else (
                base_http + 1
                if http_port is not None
                else self.config.get("ws_port", base_http + 1)
            )
        )
        self.ws_port = resolved_ws
        self.http_port = base_http
        self._reload_script = _ReloadHandler.reload_script_template.format(ws_port=self.ws_port)
        # Dev server always uses local root_url for absolute asset/page URLs.
        self._root_url = f"http://localhost:{self.http_port}"
        self._observer: Observer | None = None
        self._ws_clients: set = set()
        self._loop = asyncio.new_event_loop()
        self._rebuilding = False
        self._last_rebuild_at = 0.0
        self._last_signature: tuple | None = None
        self._debounce_seconds = 0.05
        self._post_build_delay = 0.05

    def start(
        self, include_drafts: bool = False
    ) -> None:  # pragma: no cover - integration path
        staging = self._prepare_staging_dir()
        build_site(
            self.project_root,
            include_drafts=include_drafts,
            root_url=self._root_url,
            clean_output=True,
            output_dir_override=staging,
        )
        self._activate_staging(staging)
        self._last_signature = self._compute_signature()
        threading.Thread(target=self._start_http, daemon=True).start()
        threading.Thread(target=self._start_ws, daemon=True).start()
        self._start_watcher(include_drafts)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _start_http(self) -> None:  # pragma: no cover - integration path
        handler_cls = type(
            "_ReloadHandlerWithPort",
            (_ReloadHandler,),
            {"reload_script": self._reload_script},
        )
        handler = functools.partial(handler_cls, directory=str(self.output_dir))
        httpd = ThreadingHTTPServer(("", self.http_port), handler)
        print(f"Serving {self.output_dir} at http://localhost:{self.http_port}")
        httpd.serve_forever()

    def _start_ws(self) -> None:  # pragma: no cover - integration path
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_ws_server())
        except OSError as exc:
            print(f"WebSocket server failed to start (port {self.ws_port}): {exc}")
            return

    async def _run_ws_server(self) -> None:  # pragma: no cover - integration path
        async with websockets.serve(self._ws_handler, "0.0.0.0", self.ws_port):
            await asyncio.Future()  # Run forever

    async def _ws_handler(self, websocket):
        self._ws_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self._ws_clients.discard(websocket)

    def _broadcast_reload(self):
        message = json.dumps({"type": "reload"})
        asyncio.run_coroutine_threadsafe(self._async_broadcast(message), self._loop)

    async def _async_broadcast(self, message: str):
        stale = set()
        for ws in self._ws_clients:
            try:
                await ws.send(message)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self._ws_clients.discard(ws)

    def _start_watcher(self, include_drafts: bool) -> None:
        handler = _ChangeHandler(self, include_drafts)
        observer = Observer()
        for folder in ["site", "assets", "data"]:
            watch_path = self.project_root / folder
            if watch_path.exists():
                observer.schedule(handler, str(watch_path), recursive=True)
        # Watch root for tailwind.config.js and other config files
        observer.schedule(handler, str(self.project_root), recursive=False)
        observer.start()
        self._observer = observer

    def rebuild(self, include_drafts: bool) -> None:
        now = time.time()
        if self._rebuilding or (now - self._last_rebuild_at) < self._debounce_seconds:
            return
        signature = self._compute_signature()
        if signature is not None and signature == self._last_signature:
            return
        self._rebuilding = True
        try:
            print("Change detected; rebuilding...")
            staging = self._prepare_staging_dir()
            build_site(
                self.project_root,
                include_drafts=include_drafts,
                root_url=self._root_url,
                clean_output=True,
                output_dir_override=staging,
            )
            self._activate_staging(staging)
            self._last_signature = signature
            if self._post_build_delay:
                time.sleep(self._post_build_delay)
            self._broadcast_reload()
        finally:
            self._rebuilding = False
            self._last_rebuild_at = time.time()

    def _compute_signature(self) -> tuple | None:
        entries: list[tuple] = []
        for folder in ["site", "assets", "data"]:
            root = self.project_root / folder
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_dir():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rel = path.relative_to(self.project_root)
                entries.append((str(rel), stat.st_mtime_ns, stat.st_size))
        return tuple(entries) if entries else None

    def _prepare_staging_dir(self) -> Path:
        staging = self._staging_dir
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)
        return staging

    def _activate_staging(self, staging: Path) -> None:
        target = self.output_dir
        # Atomic replace to avoid windows where output is missing.
        os.replace(staging, target)


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, server: DevServer, include_drafts: bool):
        super().__init__()
        self.server = server
        self.include_drafts = include_drafts

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Skip changes in output/staging directories
        for ignored in (
            self.server.output_dir,
            getattr(self.server, "_staging_dir", None),
        ):
            if not ignored:
                continue
            try:
                path.relative_to(ignored)
                return
            except ValueError:
                pass
        if "node_modules" in path.parts:
            return
        self.server.rebuild(self.include_drafts)
