"""Live reloading http server"""

from typing import Optional
import asyncio
from json import loads
import logging
from os import getcwd
from pathlib import Path
import re
import ssl
import webbrowser

from aiohttp import web, WSMsgType
import click
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, PatternMatchingEventHandler

import watchserver as ws


routes = web.RouteTableDef()
_path_ = Path(getcwd()).joinpath("static")

INJECT = """
<meta name="_LIVE_RELOAD_PATH_" content="{path}" />
<script id="_LIVE_RELOAD_SCRIPT_">
    const socket = new WebSocket(`ws://${{window.location.host}}/ws/_live_refresh_`);
    const reloadMeta = document.querySelector("meta[name=_LIVE_RELOAD_PATH_]")?.cloneNode();
    const reloadScript = document.getElementById("_LIVE_RELOAD_SCRIPT_")?.cloneNode(true);
    var reloadPath = reloadMeta?.content;
    socket.addEventListener("open", () => socket.send(JSON.stringify({{ type: "open", message: reloadPath }})));
    socket.addEventListener("close", () => socket.close());
    socket.addEventListener("message", (event) => {{
        const data = JSON.parse(event.data);
        switch (data.type) {{
            case "connected":
                console.warn("[Live Reload] Connected for '{path}'");
                break;
            case "update":
                if (data.message === reloadPath) {{
                    socket.send(
                    JSON.stringify({{
                        type: "fetch",
                        message: reloadPath,
                    }})
                    );
                }}
                break;
            case "moved":
                const info = data.message;
                console.warn(`[Live Reload] File renamed from ${{info.src}} to ${{info.dest}}`);
                if (info.src == reloadPath) {{
                    // Now update the paths in meta tag and script
                    reloadPath = info.dest;
                    reloadMeta.content = info.dest;
                    window.history.replaceState({{}}, `Moved to ${{info.dest}}`, `/${{info.dest}}`);
                }}
                break;
            case "dom":
                console.warn(`[Live Reload] Updating DOM`);
                const html = document.getElementsByTagName("html")[0];
                html.innerHTML = data.message;
                break;
            case "closed":
                console.error(data.message);
                socket.close();
            default:
        }}
    }});
</script>
"""

SEP = ":"
ws_logger = logging.Logger("WS")
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
sh.setFormatter(
    logging.Formatter(
        f"[\x1b[33m%(name)s\x1b[39m] %(asctime)s {SEP} %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
ws_logger.addHandler(sh)

http_logger = logging.Logger("HTTP")
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
sh.setFormatter(
    logging.Formatter(
        f"[\x1b[33m%(name)s\x1b[39m] %(asctime)s {SEP} %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
http_logger.addHandler(sh)


class ServerLogger(web.AbstractAccessLogger):
    """Abstract writer to access log."""

    @staticmethod
    def status(status: int) -> str:
        if status < 200:
            return "36"
        elif status < 300:
            return "32"
        elif status < 400:
            return "35"
        elif status < 500:
            return "31"
        elif status < 600:
            return "33"
        return "39"

    @staticmethod
    def method(method: str) -> str:
        if method == "GET":
            return "46"
        elif method == "HEAD":
            return "44"
        elif method == "POST":
            return "45"
        elif method == "PUT":
            return "43"
        elif method == "DELETE":
            return "41"
        elif method == "PATCH":
            return "43"
        return "49"

    def log(
        self,
        request: web.BaseRequest,
        response: web.StreamResponse,
        time: float,
    ) -> None:
        """Emit log to logger."""
        http_logger.info(
            "\x1b[1;%s;37m%s\x1b[22;39;49m %s \x1b[%sm%s\x1b[39m %s %s",
            ServerLogger.method(request.method),
            request.method.center(6),
            self.log_format,
            ServerLogger.status(response.status),
            response.status,
            self.log_format,
            request.path,
        )


class RefreshEventHandler(PatternMatchingEventHandler):
    """Logs all the events captured."""

    listeners: list[web.WebSocketResponse]
    """Listeners that should receive events when files change"""

    event_loop: Optional[asyncio.AbstractEventLoop]
    """Async event loop/runtime"""

    def __init__(self, *, root: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.listeners = []
        self.root = root.replace("\\", "/")

    def update(self, file: str):
        """Send a update message to all websocket listeners"""
        file = file.replace("\\", "/").lstrip(self.root.rstrip("/")).lstrip("/")
        ws_logger.info("\x1b[1mUpdate\x1b[22m %s %s", SEP, repr(file))
        with asyncio.Runner() as runner:
            for listener in self.listeners:
                runner.run(
                    listener.send_json(
                        {
                            "type": "update",
                            "message": file,
                        }
                    )
                )

    def moved(self, src: str, dest: str):
        """Send a moved message to all websocket listeners

        This will tell the browser to change the location and
        to change the id of the file it is referencing
        """

        src = src.replace("\\", "/").lstrip(self.root.rstrip("/")).lstrip("/")
        dest = dest.replace("\\", "/").lstrip(self.root.rstrip("/")).lstrip("/")

        ws_logger.info("\x1b[1m Move \x1b[22m %s %s to %s", SEP, repr(src), repr(dest))

        with asyncio.Runner() as runner:
            for listener in self.listeners:
                runner.run(
                    listener.send_json(
                        {
                            "type": "moved",
                            "message": {"src": src, "dest": dest},
                        }
                    )
                )

    @ws.debounce(0.02)
    def on_moved(self, event: FileSystemEvent) -> None:
        self.moved(event.src_path, event.dest_path)

    @ws.debounce(0.02)
    def on_modified(self, event: FileSystemEvent) -> None:
        self.update(event.src_path)


class WatchServer:
    """Live reloading http server that reloads pages when html files are
    updated. Reloads occur with WebSocket messages.
    """

    def __init__(
        self,
        root: str = ".",
        port: int = None,
        expose: bool = False,
        ssl: ssl.SSLContext | None = None,
        open: bool = False,
        host: str = None,
    ) -> None:
        self.root = root.replace("\\", "/")
        self.event_handler = RefreshEventHandler(
            root=root, patterns=[f"{self.root}/**/*.html", f"{self.root}/*.html"]
        )
        self.observer = Observer()
        self.expose = expose
        self.ssl = ssl
        self.port = port or 8080
        self.open = open
        self.host = "127.0.0.1"
        if self.expose:
            import socket

            self.host = host or socket.gethostbyname(socket.gethostname())

    def run(self):
        """Run the live reload file watching http server"""
        self.observer.schedule(self.event_handler, self.root, recursive=True)
        self.observer.start()

        app = web.Application()
        app.add_routes(
            [
                web.get("/ws/_live_refresh_", self.ws_refresh),
                web.route("*", "/", self.static_files),
                web.route("*", "/{path:.+}", self.static_files),
            ]
        )

        if self.open:
            webbrowser.open(
                f"http://{self.host}:{self.port}",
                new=2,
                autoraise=True,
            )

        try:
            web.run_app(
                app,
                host=self.host,
                port=self.port,
                access_log_class=ServerLogger,
                access_log=http_logger,
                access_log_format=SEP,
            )

            self.observer.stop()
            self.observer.join()
        except KeyboardInterrupt:
            pass
        finally:
            with asyncio.Runner() as runner:
                runner.run(self.close_all())

    async def close_all(self):
        """Close all websocket connections"""
        async with asyncio.TaskGroup() as tg:
            for listener in self.event_handler.listeners:
                tg.create_task(
                    listener.send_json(
                        {
                            "type": "closed",
                            "message": "[LiveReload] Connection lost",
                        }
                    )
                )

    def load_file(self, filename: str) -> bytes | None:
        """Load a system file and inject live reload script if it is html"""
        filename = filename.replace("\\", "/")

        path = Path(self.root).joinpath(filename)
        if path.exists():
            if path.suffix in [".html", ".htm"]:
                with path.open("r", encoding="utf-8") as file:
                    data = file.read()
                    if (
                        match := re.search(r"<\/.*head.*>", data, re.MULTILINE)
                    ) is not None:
                        start = match.start()
                        data = bytes(
                            data[0 : match.start()]
                            + (INJECT.format(path=filename))
                            + data[start:],
                            encoding="utf-8",
                        )
                    elif (match := re.search("<html.+>", data)) is not None:
                        end = match.end()
                        data = bytes(
                            data[0:end]
                            + f"<head>{INJECT.format(path=filename)}</head>"
                            + data[end:],
                            encoding="utf-8",
                        )
                    else:
                        data = bytes(
                            data + INJECT.format(filename=filename),
                            encoding="utf-8",
                        )
            else:
                with path.open("rb") as file:
                    data = file.read()
            return data
        return None

    async def ws_refresh(self, request: web.Request):
        """Setup a websocket connection with a page and send update messages
        when a file is updated. The message will include/allow for the update
        of the inner data of the DOM.
        """

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.event_handler.listeners.append(ws)

        async for msg in ws:
            # ws.__next__() automatically terminates the loop
            # after ws.close() or ws.exception() is called
            if msg.type == WSMsgType.TEXT:
                data = loads(msg.data)
                mtype = data.get("type")
                message = data.get("message", "")

                if mtype is None:
                    await ws.send_json(
                        {
                            "type": "error",
                            "message": "invalid websocket message format: expected json with type field",
                        },
                        True,
                    )

                if mtype == "close":
                    await ws.close()
                elif mtype == "open":
                    await ws.send_json({"type": "connected"})
                elif mtype == "fetch":
                    if (file := self.load_file(message)) is not None:
                        await ws.send_json({"type": "dom", "message": file.decode()})
            elif msg.type == WSMsgType.CLOSE:
                await ws.close()
            elif msg.type == WSMsgType.ERROR:
                ws_logger.error(f"ws connection closed with exception {ws.exception()}")

        ws_logger.info("Closed Connection")
        self.event_handler.listeners.remove(ws)
        return ws

    async def static_files(self, request):
        """Serve static files to the browser

        If the static file is html then it will have a script injected into
        the file to connect via websocket and refresh the page when file
        updates ccur
        """

        # TODO: Change to stream the data instead
        path_arg = request.match_info.get("path", "")
        path = Path(self.root).joinpath(path_arg)
        if path.exists() and path.is_file():
            return web.Response(
                body=self.load_file(path_arg), headers={"Content-Type": ""}
            )

        if (
            path.joinpath("index.html").exists()
            and path.joinpath("index.html").is_file()
        ):
            return web.Response(
                body=self.load_file(str(Path(path_arg).joinpath("index.html"))),
                headers={"Content-Type": "text/html"},
            )

        return web.HTTPNotFound()


@click.command()
@click.argument("root", required=False)
@click.option(
    "-x",
    "--expose",
    is_flag=True,
    default=False,
    help="Expose the server to the local network",
)
@click.option(
    "-h",
    "--host",
    default=None,
    help="When expose is set, this is the host instead of the current IP",
)
@click.option(
    "-p",
    "--port",
    type=int,
    help="Define what port the server should host on",
)
@click.option(
    "-o",
    "--open",
    is_flag=True,
    help="Open webbrowser to hosted url",
)
def main(
    root: str,
    expose: bool = False,
    port: int = None,
    host: str = None,
    open: bool = False,
):
    """Opinionated live reload server written in python using WebSockets

    \x1b[1;36mNOTE\x1b[0m

    - The server uses file based routing\n
    - Routing of `path/index.html` can be shortened to `path/` or just `path`\n
    - No files outside the root directory that is being served may be accessed

    \x1b[1;33mWARNING\x1b[0m

    This is not a production grade server. It must only be used for development
    as there are countless security risks that come with using this server
    in production.
    """

    WatchServer(root or ".", port, expose=expose, open=open, host=host).run()


if __name__ == "__main__":
    main()
