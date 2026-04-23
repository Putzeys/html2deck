#!/usr/bin/env python3
"""
html2deck server — Preview + Export interface.

Usage:
    python server.py                  # start on port 3005
    python server.py --port 8080      # custom port
"""

import argparse
import http.server
import json
import mimetypes
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

PROJECT_DIR = Path(__file__).parent.resolve()
PREVIEW_HTML = (PROJECT_DIR / "preview.html").resolve()
DECK_SCRIPT = (PROJECT_DIR / "html2deck.py").resolve()

# Temp dir for uploaded files
UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="html2deck_uploads_"))


class Handler(http.server.BaseHTTPRequestHandler):

    # Track the current HTML file's directory for resolving relative assets
    current_dir = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self._send_file(PREVIEW_HTML, "text/html")
        elif path == "/api/open":
            self._handle_open(params)
        elif path == "/api/serve":
            self._handle_serve(params)
        elif path == "/export":
            self._handle_export(params)
        elif path.startswith("/asset/"):
            self._handle_asset(path[7:])  # strip "/asset/"
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            self._handle_upload(parse_qs(parsed.query))
        else:
            self.send_error(404)

    # ── API: validate a file path ────────────────────────────────

    def _handle_open(self, params):
        raw = params.get("path", [None])[0]
        if not raw:
            self.send_error(400, "Missing path"); return

        p = Path(unquote(raw)).expanduser().resolve()
        if not p.is_file() or p.suffix.lower() != ".html":
            self.send_error(404, "HTML file not found"); return

        self._send_json({"path": str(p), "name": p.name, "dir": str(p.parent)})

    # ── API: serve any local file (for iframe + assets) ──────────

    def _handle_serve(self, params):
        raw = params.get("path", [None])[0]
        if not raw:
            self.send_error(400); return

        p = Path(unquote(raw)).resolve()

        # If it's a known HTML file, also allow serving assets from its directory
        # Check for relative asset requests via Referer
        if not p.is_file():
            self.send_error(404); return

        ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        self._send_file(p, ct)

    # ── API: upload file from drag-drop ──────────────────────────

    def _handle_upload(self, params):
        name = params.get("name", ["upload.html"])[0]
        name = Path(unquote(name)).name  # sanitize

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        dest = UPLOAD_DIR / name
        dest.write_bytes(body)

        self._send_json({"path": str(dest), "name": name})

    # ── API: serve relative assets from the HTML's directory ────

    def _handle_asset(self, rel_path):
        if not Handler.current_dir:
            self.send_error(404); return
        p = (Path(Handler.current_dir) / unquote(rel_path)).resolve()
        # Security: stay within the HTML's directory tree
        if not str(p).startswith(str(Handler.current_dir)):
            self.send_error(403); return
        if not p.is_file():
            self.send_error(404); return
        ct = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        self._send_file(p, ct)

    # ── Export ────────────────────────────────────────────────────

    def _handle_export(self, params):
        raw = params.get("path", [None])[0]
        fmt = params.get("format", ["pdf"])[0]
        zoom = params.get("zoom", ["100"])[0]
        scale = params.get("scale", ["2"])[0]
        duration = params.get("duration", ["4"])[0]

        if not raw:
            self.send_error(400, "Missing path"); return
        if fmt not in ("pdf", "pptx", "mp4"):
            self.send_error(400, "Invalid format"); return

        html_path = Path(unquote(raw)).resolve()
        if not html_path.is_file():
            self.send_error(404, "File not found"); return

        print(f"  Exporting {html_path.name} → {fmt.upper()} (zoom={zoom}%, scale={scale}x)...")

        with tempfile.TemporaryDirectory(prefix="html2deck_") as tmpdir:
            output_base = str(Path(tmpdir) / "export")
            cmd = [
                sys.executable, str(DECK_SCRIPT),
                str(html_path),
                "-f", fmt,
                "--zoom", zoom,
                "--scale", scale,
                "-o", output_base,
            ]
            if fmt == "mp4":
                cmd += ["--duration", duration]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600,
                )
            except subprocess.TimeoutExpired:
                self.send_error(504, "Export timed out"); return

            output_file = Path(f"{output_base}.{fmt}")
            if not output_file.exists():
                err = result.stderr[-500:] if result.stderr else result.stdout[-500:]
                print(f"  Export failed: {err}")
                self.send_error(500, "Export failed"); return

            data = output_file.read_bytes()

        ct = {
            "pdf": "application/pdf",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "mp4": "video/mp4",
        }
        filename = html_path.stem + "." + fmt

        self.send_response(200)
        self.send_header("Content-Type", ct.get(fmt, "application/octet-stream"))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        print(f"  {fmt.upper()} sent ({len(data)/1048576:.1f} MB)")

    # ── Helpers ───────────────────────────────────────────────────

    def _send_json(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, content_type):
        data = Path(path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        pass


def main():
    p = argparse.ArgumentParser(prog="html2deck server")
    p.add_argument("--port", type=int, default=3005)
    args = p.parse_args()

    srv = http.server.HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"html2deck server")
    print(f"  URL:     http://localhost:{args.port}")
    print(f"  Paste any HTML file path or drag-drop into the browser")
    print(f"  Ctrl+C to stop\n")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
