from __future__ import annotations
import datetime
import email
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import posixpath
from threading import Thread
from time import sleep
from typing import BinaryIO, Callable, Literal
from re import match
import io
import urllib
import string

from watchdog.observers import Observer
from .watchdog import LiveWatchHandler

# Reference: https://docs.python.org/3/library/http.server.html

LOCALHOST: tuple[Literal['127.0.0.1', 'localhost']] = ("127.0.0.1", "localhost")
SERVER_PORT = 3031
PORT_RANGE = [49200, 65535]

livereload_script = string.Template("""
<script defer>
    var livereload = function() {
        var req = new XMLHttpRequest();
        req.onloadend = function() {
            // File has been changed reload the server
            if (parseInt(this.responseText) === 1) {
                location.reload();
                return;
            }

            // Queue next livreload request
            var launchNext = livereload.bind(this);
            if (this.status === 200) {
                // If server is still connected make another request
                launchNext();
            } else if (this.status !== 0) {
                // If server is still connected wait 3 seconds
                setTimeout(launchNext, 3000);
            } else {
                console.warn("[Live Reload] Detached: Server is down");
            }
        };
        req.open("GET", '/livereload/${path}');
        req.send();
    }
    livereload();
    console.warn("[Live Reload] Attached: '/${path}'");
</script>
""")

def default(src):
    return True

def translate_path(root, src) -> str:
    return posixpath.normpath(src.lstrip(root)).rstrip("index.html").replace("\\", "/")

class LiveServer:
    """Live reload server."""
    def __init__(
        self,
        *watch: str,
        root: str = "",
        host: str = LOCALHOST[0],
        port: int = SERVER_PORT,
        cb_update: Callable = None,
        cb_remove: Callable = None,
        cb_create: Callable = None,
    ) -> None:
        self.host = host
        self.port = port
        self.cache: dict[str, bool] = {}

        self.server = LiveServerThread(
            self.host,
            self.port,
            daemon=True,
            cache=self.cache,
            directory=root
        )


        # Setup function that sends the file_path to a callback and ensures
        # that it either returns a bool or defaults to False
        def update_cache(src: str, clbk: Callable | None):
            path = translate_path(root, src)
            result = clbk(path)
            if isinstance(result, bool):
                self.cache[path] = result

        # Assign callbacks that handle updating the files and restarting the server
        event_handler = LiveWatchHandler(
            lambda src:  update_cache(src, cb_create or default),
            lambda src: update_cache(src, cb_update or default),
            lambda src: update_cache(src, cb_remove or default)
        )
        self.watchdog = Observer()

        # Add recursive watch directories to watchdog
        if len(watch) == 0:
            print(f"Watching {posixpath.normpath(root)}")
            self.watchdog.schedule(event_handler, posixpath.normpath(root), recursive=True)
        else:
            print(f"Watching paths:")
            for path in watch:
                path = posixpath.join(root, path)
                print(f"  - {posixpath.normpath(path)}")
                self.watchdog.schedule(event_handler, posixpath.normpath(path), recursive=True)

    def run(self):
        """Start the server and file watcher. Creates infinite loop that is interuptable."""
        self.start()
        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def start(self):
        """Start the server and file watcher."""
        self.server.start()
        self.watchdog.start()

    def stop(self):
        """Stop the server and file watcher."""
        self.server.stop()
        self.watchdog.stop()

class LiveServerThread(Thread):
    """Thread for the server to allow for serve_forever without interfering with the main thread."""

    def __init__(
        self,
        host: str = "localhost",
        port=PORT_RANGE[0],
        *args,
        cache: dict[str, bool],
        directory: str = "",
        **kwargs
    ):
        super(LiveServerThread, self).__init__(*args, **kwargs, kwargs={"cache": cache})
        self.server = Server(cache, directory, host=host, port=port)

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

    def __init__(
        self,
        request,
        client_address,
        server,
        *,
        directory: str | None = ""
    ) -> None:
        super().__init__(request, client_address, server, directory=directory)

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        error_page = Path(self.server.directory).joinpath(f"{code}.html")
        if error_page.is_file():
            self.send_response(code)
            self.end_headers()
            with open(error_page, "r", encoding="utf-8") as custom_error_file:
                self.wfile.write(custom_error_file.read().encode("utf-8"))
            return
        return super().send_error(code, message, explain)

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        if "/livereload/" not in self.requestline:
            return super().log_request(code, size)

    def send_head(self, live_reload: str) -> io.BytesIO | BinaryIO | None:
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                            parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        if path.endswith("/"):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            if not Path(self.path).is_file() or self.path.endswith((".html", ".htm")):
                self.send_header("Content-Length", str(fs[6] + len(live_reload)))
            else:
                self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified",
                self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def do_GET(self) -> None:
        path = self.translate_path(self.path).replace("\\", "/")
        live_reload = match(r"/?livereload/(?P<path>.*)", path)
        if live_reload is not None:
            file_path = live_reload.group("path") if live_reload.group("path") != "" else "/"
            self.send_response(200)
            self.end_headers()
            code = 0
            try:
                if file_path in self.server.cache:
                    if self.server.cache[file_path]:
                        self.server.cache[file_path] = False
                        code = 1
                    else:
                        code = 0
            except: pass

            self.wfile.write(bytes(f"{code}", "utf-8"))
        else:
            # Same as super().do_GET() except a live reload script is injected
            self.path = posixpath.join(self.server.directory.strip("/"), self.path.lstrip("/"))
            live_reload = livereload_script.substitute(path=path.lstrip('/'))
            file = self.send_head(live_reload)
            if file:
                try:
                    if not Path(self.path).is_file() or self.path.endswith((".html", ".htm")):
                        data =  f"{file.read().decode()}{live_reload}"
                        self.wfile.write(bytes(data, "utf-8"))
                    else:
                        self.copyfile(file, self.wfile)
                finally:
                    file.close()

class Server(ThreadingHTTPServer):
    """Threaded live reload server."""

    def __init__(
        self,
        cache: dict[str, bool],
        directory: str,
        *,
        host: str = "localhost",
        port=PORT_RANGE[0],
    ):

        super().__init__((host, port), ServiceHandler)
        self.host = host
        self.port = port
        self.is_active = False
        self.full_url = f"http://{host}:{port}/"
        self.cache = cache
        self.directory = directory

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

    def url(self, host: str) -> str:
        """Get the base url of the server."""
        return f"http://{host}:{self.server_port}/"

    def start(self):
        """Start the server."""
        self.serve_forever()

    def stop(self):
        """Stop the server."""
        self.shutdown()
        self.server_close()
