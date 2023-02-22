from inspect import signature
from threading import Timer
import time
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import *

observer = Observer()
Callbacks = dict[str, dict[str, Callable]]

def debounce(wait):
    """Debounce or limit the calls to a function."""

    def decorator(func):
        """Decorator for the function."""

        sig = signature(func)
        caller = {}

        def debounced(*args, **kwargs):
            nonlocal caller

            try:
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                called_args = func.__name__ + str(dict(bound_args.arguments))
            except:
                called_args = ''

            t_ = time.time()

            def call_it(key):
                try:
                    # always remove on call
                    caller.pop(key)
                except:
                    pass

                func(*args, **kwargs)

            try:
                # Always try to cancel timer
                caller[called_args].cancel()
            except:
                pass

            caller[called_args] = Timer(wait, call_it, [called_args])
            caller[called_args].start()

        return debounced

    return decorator

WAIT = 0.1

class LiveWatchHandler(FileSystemEventHandler):
    """Handler for live reload Watchdog."""

    def __init__(
        self,
        create: Callable,
        update: Callable,
        remove: Callable,
    ) -> None:
        self._create = create
        self._update = update
        self._remove = remove

    @debounce(WAIT)
    def on_any_event(self, event: FileSystemEvent):
        pass

    @debounce(WAIT)
    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        if isinstance(event, FileModifiedEvent):
            self._update(event.src_path)

    @debounce(WAIT)
    def on_created(self, event):
        if isinstance(event, FileModifiedEvent):
            self._create(event.src_path)

    @debounce(WAIT)
    def on_deleted(self, event):
        if isinstance(event, FileDeletedEvent):
            self._update(event.src_path)
