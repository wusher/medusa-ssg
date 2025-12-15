"""Development server for Medusa.

This module provides a development server with live reload functionality.
It serves the built site over HTTP and uses WebSockets to notify clients of changes.

Key classes:
- DevServer: Main class for running the development server.
- _ReloadHandler: HTTP request handler that injects reload script.
- _ChangeHandler: File system event handler for triggering rebuilds.
"""

from __future__ import annotations

import asyncio
import json
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

    reload_script = """
    <script>
    (() => {
      const ws = new WebSocket('ws://' + location.hostname + ':4001');
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data || '{}');
        if (data.type === 'reload') location.reload();
      };
    })();
    </script>
    """

    def end_headers(self):
        # Ensure CORS for dev
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if path.endswith(".html") and Path(path).exists():
            content = Path(path).read_text(encoding="utf-8")
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

    def __init__(self, project_root: Path):
        """Initialize the development server.

        Args:
            project_root: Root directory of the project.
        """
        self.project_root = project_root
        self.config = load_config(project_root)
        self.output_dir = project_root / self.config.get("output_dir", "output")
        self.ws_port = self.config.get("ws_port", 4001)
        self.http_port = int(self.config.get("port", 4000))
        self._observer: Observer | None = None
        self._ws_clients: set = set()
        self._loop = asyncio.new_event_loop()

    def start(
        self, include_drafts: bool = False
    ) -> None:  # pragma: no cover - integration path
        build_site(self.project_root, include_drafts=include_drafts)
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
        handler = _ReloadHandler
        handler.directory = str(self.output_dir)
        httpd = ThreadingHTTPServer(("", self.http_port), handler)
        print(f"Serving {self.output_dir} at http://localhost:{self.http_port}")
        httpd.serve_forever()

    def _start_ws(self) -> None:  # pragma: no cover - integration path
        asyncio.set_event_loop(self._loop)
        start_server = websockets.serve(self._ws_handler, "0.0.0.0", self.ws_port)
        self._loop.run_until_complete(start_server)
        self._loop.run_forever()

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
        observer.schedule(handler, str(self.project_root), recursive=False)
        observer.start()
        self._observer = observer

    def rebuild(self, include_drafts: bool) -> None:
        print("Change detected; rebuilding...")
        build_site(self.project_root, include_drafts=include_drafts)
        self._broadcast_reload()


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, server: DevServer, include_drafts: bool):
        super().__init__()
        self.server = server
        self.include_drafts = include_drafts

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self.server.output_dir in path.parents or path == self.server.output_dir:
            return
        self.server.rebuild(self.include_drafts)
