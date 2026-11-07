"""Local mock ATS: simple application form with a confirmation page.

Usage:
    python test_sites/simple_form/server.py --port 8765
"""

from __future__ import annotations

import argparse
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SITE_DIR = Path(__file__).resolve().parent


class SimpleFormHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_file(SITE_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/confirmation":
            self._send_file(SITE_DIR / "confirmation.html", "text/html; charset=utf-8")
        else:
            self.send_error(404, "not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.rstrip("/") != "/submit":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        self.send_response(303)
        self.send_header("Location", "/confirmation?ref=APP-1001")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        if getattr(self.server, "quiet", False):
            return
        super().log_message(format, *args)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class SimpleFormServer(ThreadingHTTPServer):
    quiet = True
    allow_reuse_address = True


def start_simple_form(
    host: str = "127.0.0.1", port: int = 0, *, quiet: bool = True
) -> tuple[SimpleFormServer, str]:
    server = SimpleFormServer((host, port), SimpleFormHandler)
    server.quiet = quiet
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_host, bound_port = server.server_address[:2]
    url = f"http://{bound_host}:{bound_port}/"
    return server, url


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the simple mock ATS form")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server, url = start_simple_form(args.host, args.port, quiet=False)
    print(f"Simple form at {url}")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
