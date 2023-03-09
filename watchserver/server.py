from __future__ import annotations

from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Any, BinaryIO
from queue import Queue
import urllib
import io

from threading import Thread
from re import match
import os

from .util import ServerPath, PORT_RANGE, livereload_script, translate_path, LOCALHOST

# Reference: https://docs.python.org/3/library/http.server.html


class LiveServerThread(Thread):
    """Thread for the server to allow for serve_forever without interfering with the
    main thread.
    """

    def __init__(
        self,
        host: str = "localhost",
        port=PORT_RANGE[0],
        *args,
        reloads: Queue[ServerPath],
        directory: str = "",
        base: str = "",
        **kwargs,
    ):
        super(LiveServerThread, self).__init__(*args, **kwargs)
        self.server = Server(reloads, directory, base, host=host, port=port)

    def suppress(self):
        """Surpress all logs from the server."""
        self.server.logging = False

    def logging(self):
        """Enable all logs from the server."""
        self.server.logging = True

    def run(self) -> None:
        self.server.start()

    def restart(self):
        """Restart the server."""

        self.server.shutdown()
        self.server.server_close()
        self.server.server_activate()
        self.server.serve_forever()

    def stop(self):
        """Stop the server."""
        self.server.stop()

    def stopped(self):
        """Status of if the server is stopped or not."""
        return self.server.active()


class ServiceHandler(SimpleHTTPRequestHandler):
    """Handler for the Server requests."""

    extensions_map = _encodings_map_default = {
        '.gz': 'application/gzip',
        '.Z': 'application/octet-stream',
        '.bz2': 'application/x-bzip2',
        '.xz': 'application/x-xz',
        '.js': 'application/javascript',
    }

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
        path: str | None = None,
    ) -> None:
        error_page = ServerPath(self.server.root, self.server.epath, f"{code}.html")
        if error_page.isfile():
            live_reload = livereload_script.substitute(path=path or self.path)
            with open(error_page.platform(), "r", encoding="utf-8") as custom_error_file:
                data = custom_error_file.read()
                self.send_response(code)
                self.send_header("Content-Length", str(len(live_reload) + len(data)))
                self.no_cache_headers()
                self.end_headers()
                self.wfile.write(f"{data}{live_reload}".encode("utf-8"))
            return
        return super().send_error(code, message, explain)

    def no_cache_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def log_error(self, format: str, *args: Any) -> None:
        if self.server.logging:
            return super().log_error(format, *args)

    def log_message(self, format: str, *args: Any) -> None:
        if self.server.logging:
            return super().log_message(format, *args)

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        if "/livereload/" not in self.requestline and self.server.logging:
            return super().log_request(code, size)

    def send_head(self, live_reload: str, request_path: str) -> io.BytesIO | BinaryIO | None:
        path = self.translate_path(self.path)
        f = None
        if ServerPath(path).isdir():
            parts = urllib.parse.urlsplit(request_path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/', parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.no_cache_headers()
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = ServerPath(path, index)
                if index.isfile():
                    path = index.posix()
                    break
            else:
                return self.list_directory(path)

        ctype = self.guess_type(path)
        if ServerPath(path).with_suffix(".js").isfile():
            ctype = "application/javascript"
            path = ServerPath(path).with_suffix(".js").posix()
        elif path.endswith("/"):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found", path)
            return None
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found", path)
            return None

        try:
            fs = os.fstat(f.fileno())
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            if self.path.endswith((".html", ".htm")) or not ServerPath(self.path).lstrip().isfile():
                self.send_header("Content-Length", str(fs[6] + len(live_reload)))
            else:
                self.send_header("Content-Length", str(fs[6]))
            self.no_cache_headers()
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def lr_script(self) -> str:
        """Construct the live reload script html element based on the current path."""
        return livereload_script.substitute(path=translate_path(self.server.root, self.path))

    def do_GET(self) -> None:
        live_reload = match(r"/?livereload/(?P<path>.*)", self.path)
        if live_reload is not None:
            file_path = translate_path(self.server.root, live_reload.group("path"))
            self.send_response(200)
            self.end_headers()

            code = 0
            try:
                while self.server.reloads.qsize() != 0:
                    reload = self.server.reloads.get(timeout=5)
                    if match(f"^{reload.regex()}$", file_path) is not None:
                        code = 1
                    self.server.reloads.task_done()
            except Exception:
                pass
            self.wfile.write(bytes(f"{code}", "utf-8"))
        else:
            # Same as super().do_GET() except a live reload script is injected
            request_path = str(self.path)
            self.path = ServerPath(self.server.root, self.path).posix()
            live_reload = self.lr_script()
            file = self.send_head(live_reload, request_path)
            if file:
                try: 
                    if self.path.endswith((".html", ".htm")) or not ServerPath(self.path).lstrip().isfile():
                        data = file.read() + bytes(live_reload, "utf-8")
                        self.wfile.write(data)
                    else:
                        self.copyfile(file, self.wfile)
                finally:
                   file.close()


class Server(ThreadingHTTPServer):
    """Threaded live reload server."""

    def __init__(
        self,
        reloads: Queue[ServerPath],
        root: str,
        base: str,
        *,
        host: str = "localhost",
        port=PORT_RANGE[0],
    ):

        super().__init__((host, port), ServiceHandler)
        self.host = host
        self.port = port
        self.is_active = False
        self.full_url = f"http://{host}:{port}/"
        self.reloads = reloads
        self.root = root
        self.epath = base
        self.logging = True

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        self.is_active = True
        return super().serve_forever(poll_interval)

    def shutdown(self) -> None:
        self.is_active = False
        super().shutdown()
        self.server_close()

    def active(self) -> bool:
        """Whether the server is up and active."""
        return self.is_active

    def url(self, host: str | None = None) -> str:
        """Get the base url of the server."""
        return f"http://{host or LOCALHOST[1]}:{self.server_port}/"

    def start(self):
        """Start the server."""
        self.serve_forever()

    def stop(self):
        """Stop the server."""
        self.shutdown()
        self.server_close()
