#!/usr/bin/env python3
"""
html2deck server — Preview + Export interface.

Usage:
    python server.py /path/to/slides.html
    python server.py /path/to/slides.html --port 3005
"""

import argparse
import http.server
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PROJECT_DIR = Path(__file__).parent.resolve()
PREVIEW_HTML = (PROJECT_DIR / "preview.html").resolve()
DECK_SCRIPT = (PROJECT_DIR / "html2deck.py").resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    html_file = None
    serve_dir = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.serve_dir), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/preview"):
            self._serve_preview()
        elif parsed.path == "/export":
            self._handle_export(parse_qs(parsed.query))
        else:
            super().do_GET()

    def _serve_preview(self):
        html_name = Path(self.html_file).name
        html_path = str(Path(self.html_file).resolve())

        tpl = PREVIEW_HTML.read_text(encoding="utf-8")
        page = tpl.replace("{{HTML_NAME}}", html_name).replace("{{HTML_PATH}}", html_path)

        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_export(self, params):
        fmt = params.get("format", ["pdf"])[0]
        zoom = params.get("zoom", ["100"])[0]
        duration = params.get("duration", ["4"])[0]

        if fmt not in ("pdf", "pptx", "mp4"):
            self.send_error(400, "Invalid format")
            return

        print(f"  Exporting {fmt.upper()} (zoom={zoom}%)...")

        with tempfile.TemporaryDirectory(prefix="html2deck_") as tmpdir:
            output_base = str(Path(tmpdir) / "export")
            cmd = [
                sys.executable, str(DECK_SCRIPT),
                str(Path(self.html_file).resolve()),
                "-f", fmt,
                "--zoom", zoom,
                "-o", output_base,
            ]
            if fmt == "mp4":
                cmd += ["--duration", duration]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=600,
                )
            except subprocess.TimeoutExpired:
                self.send_error(504, "Export timed out")
                return

            output_file = Path(f"{output_base}.{fmt}")
            if not output_file.exists():
                err = result.stderr[-500:] if result.stderr else result.stdout[-500:]
                print(f"  Export failed: {err}")
                self.send_error(500, f"Export failed")
                return

            data = output_file.read_bytes()

        ct = {
            "pdf": "application/pdf",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "mp4": "video/mp4",
        }
        filename = Path(self.html_file).stem + "." + fmt

        self.send_response(200)
        self.send_header("Content-Type", ct.get(fmt, "application/octet-stream"))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        print(f"  {fmt.upper()} sent ({len(data)/1048576:.1f} MB)")

    def log_message(self, fmt, *args):
        pass  # silent


def main():
    p = argparse.ArgumentParser(prog="html2deck server")
    p.add_argument("input", help="HTML file to preview")
    p.add_argument("--port", type=int, default=3005)
    args = p.parse_args()

    html_path = Path(args.input).resolve()
    if not html_path.is_file():
        print(f"Not found: {html_path}")
        sys.exit(1)

    Handler.html_file = str(html_path)
    Handler.serve_dir = str(html_path.parent)

    srv = http.server.HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"html2deck server")
    print(f"  File:    {html_path.name}")
    print(f"  URL:     http://localhost:{args.port}")
    print(f"  Ctrl+C to stop\n")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
