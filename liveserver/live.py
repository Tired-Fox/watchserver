from time import sleep
from typing import Callable
import webbrowser

from .util import ServerPath, default, LOCALHOST, SERVER_PORT
from .server import LiveServerThread
from .watch import LiveWatchHandler
from queue import Queue

from watchdog.observers import Observer

__all__ = [
    "LiveCallback",
    "LiveServer"
]

class LiveCallback:
    """Live reloading callbacks for when files are created, updated, or removed.
    
    Inherit from this class and override the three methods, `create`, `update`, and `remove`
    as you need to. If you wish to trigger logic on every call you can do that then call
    the super classes method.

    This base class uses great default returns that live reload based on files paths and when
    static files, `css` and `js`, are modified. The default method will parse the url, cache key,
    based on the files path. Static file changes are also applied to the cache key of every page
    that has already been visited, If you need different functionality make sure to override the
    default.
    """

    def create(self, root: str, file: str) -> list[str]:
        """Callback for the liveserver for when a new file is created.

        Args:
            root (str): Path to where the server is serving from the cwd.
            file (str): Path to the file that was created from the cwd.
        
        Returns:
            tuple[bool, str|None, str|None]: Boolean of whether the page should be live reloaded
                and a str of the files url. These two are used in the server cache which then live
                reloads the page. Finally the last str is a file matching pattern. This matches the
                keys in the cache and marks them as needing a live reload. This is most usefull for
                when static files are updated and you want the current page to update. '**' will
                make sure that any page is updated. Otherwise the specific glob pattern is used. For
                either string value return `''` or `None` to not live reload for that key or for a
                pattern.
        """
        return default(root, file)

    def update(self, root: str, file: str) -> list[str]:
        """Callback for the liveserver for when a new file is updated.

        Args:
            root (str): Path to where the server is serving from the cwd.
            file (str): Path to the file that was updated from the cwd.
        
        Returns:
            tuple[bool, str|None, str|None]: Boolean of whether the page should be live reloaded
                and a str of the files url. These two are used in the server cache which then live
                reloads the page. Finally the last str is a file matching pattern. This matches the
                keys in the cache and marks them as needing a live reload. This is most usefull for
                when static files are updated and you want the current page to update. '**' will
                make sure that any page is updated. Otherwise the specific glob pattern is used. For
                either string value return `''` or `None` to not live reload for that key or for a
                pattern.
        """
        return default(root, file)

    def remove(self, root: str, file: str) -> list[str]:
        """Callback for the liveserver for when a new file is removed.

        Args:
            root (str): Path to where the server is serving from the cwd.
            file (str): Path to the file that was removed from the cwd.
        
        Returns:
            tuple[bool, str|None, str|None]: Boolean of whether the page should be live reloaded
                and a str of the files url. These two are used in the server cache which then live
                reloads the page. Finally the last str is a file matching pattern. This matches the
                keys in the cache and marks them as needing a live reload. This is most usefull for
                when static files are updated and you want the current page to update. '**' will
                make sure that any page is updated. Otherwise the specific glob pattern is used. For
                either string value return `''` or `None` to not live reload for that key or for a
                pattern.
        """
        return default(root, file)

class LiveServer:
    """Live reload server. Contains a threaded server, a watchdog observer instance, and a Queue.
    
    The watchdog observer watches the patch paths and calls create, update, and remove callbacks for
    the respective file events. These callbacks can in turn return a list of paths/urls that are
    added to the queue. When a live reload request is sent the server pops all paths from the queue
    and checks to see if the request path matches the path. If so a reload response is sent.
    Otherwise a no-reload response is sent.
    
    The server also checks the base path for custom error files matching the error code. If a 404
    error is sent then the server will look for a `404.html` file in the base path.
    """

    def __init__(
        self,
        *watch: str,
        root: str = "",
        base: str = "",
        auto_open: bool = False,
        host: str = LOCALHOST[0],
        port: int = SERVER_PORT,
        surpress: bool = False,
        live_callback: LiveCallback = LiveCallback()
    ) -> None:
        self.root = root
        self.host = host
        self.port = port
        self.auto_open = auto_open
        self.reloads: Queue = Queue()

        self.server_thread = LiveServerThread(
            self.host, self.port, daemon=True, reloads=self.reloads, directory=root, base=base
        )

        if surpress:
            self.server_thread.surpress()

        # Setup function that sends the file_path to a callback and ensures
        # that it either returns a bool or defaults to False
        def update_file(src: str, clbk: Callable | None):
            paths = clbk(root, src)
            for path in paths or []:
                self.reloads.put(ServerPath(path))

        # Assign callbacks that handle updating the files and restarting the server
        event_handler = LiveWatchHandler(
            lambda src: update_file(src, live_callback.create),
            lambda src: update_file(src, live_callback.update),
            lambda src: update_file(src, live_callback.remove),
        )
        self.watchdog = Observer()

        # Add recursive watch directories to watchdog
        if len(watch) == 0:
            if not surpress:
                print(f"Watching path {ServerPath(root).posix()!r}")
            self.watchdog.schedule(event_handler, ServerPath(root).platform(), recursive=True)
        else:
            if not surpress:
                print("Watching paths:")
            for path in watch:
                path = ServerPath(root, path).posix()
                if not surpress:
                    print(f"  - {path.posix()!r}")
                self.watchdog.schedule(event_handler, path, recursive=True)

    def surpress(self):
        """Surpress all logs from the server."""
        self.server_thread.surpress()

    def logging(self):
        """Enable all logs from the server."""
        self.server_thread.logging()

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
        self.server_thread.start()
        self.watchdog.start()
        
        if self.auto_open:
            webbrowser.open_new_tab(
                self.server_thread.server.url(LOCALHOST[1]) + f"{ServerPath(self.root).lstrip()}"
            )

    def stop(self):
        """Stop the server and file watcher."""
        self.server_thread.stop()
        self.watchdog.stop()
        self.reloads.join()