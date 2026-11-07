"""Serve a mock ATS directory on localhost."""

from __future__ import annotations

import argparse
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def make_handler(site_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            rel = urlparse(self.path).path
            if rel in {"/", ""}:
                rel = "/index.html"
            dest = (site_dir / rel.lstrip("/")).resolve()
            if not str(dest).startswith(str(site_dir.resolve())) or not dest.is_file():
                self.send_error(404)
                return
            data = dest.read_bytes()
            mime = mimetypes.guess_type(dest.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if length:
                self.rfile.read(length)
            self.send_response(303)
            self.send_header("Location", "/confirmation.html")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    return Handler


class QuietServer(ThreadingHTTPServer):
    allow_reuse_address = True


def start_site(site_dir: Path, host: str = "127.0.0.1", port: int = 0) -> tuple[QuietServer, str]:
    server = QuietServer((host, port), make_handler(Path(site_dir)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    bound_host, bound_port = server.server_address[:2]
    return server, f"http://{bound_host}:{bound_port}/"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server, url = start_site(args.site, port=args.port)
    print(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
