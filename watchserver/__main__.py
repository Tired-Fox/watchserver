#!/usr/bin/env python
from __future__ import annotations

from time import sleep
import click

from watchserver import __version__, LiveServer

HELP = {
    "root": "path where the server should attach",
    "errors": "path where the server will find custom error files (ex. 404.html).",
    "serve": "port that the server will serve to",
    "watch": "list of paths to watch. Repeat the command for each entry to the list",
    "version": "Version of mophidian",
    "silent": "Surpress all logs from the server and file watcher",
    "open": "Toggle on auto open in browser.",
    "ignore": "list of ignore patterns to apply to file watcher. Repeat command for each entry",
}


@click.option("-r", "--root", default="", help=HELP["root"])
@click.option("-e", "--errors", default="", help=HELP["errors"])
@click.option("-p", "--port", default=3031, help=HELP["serve"])
@click.option("-w", "--watch", multiple=True, default=[], help=HELP["watch"])
@click.option("-i", "--ignore", multiple=True, default=[], help=HELP["ignore"])
@click.option("-v", "--version", flag_value=True, default=False, help=HELP["version"])
@click.option("-o", "--open", flag_value=True, default=False, help=HELP["open"])
@click.option("-s", "--silent", flag_value=True, default=False, help=HELP["silent"])
@click.command(name="serve")
def serve(
    root: str = "",
    errors: str = "",
    port: int = 3031,
    watch: list[str] = [],
    ignore: list[str] = [],
    version: bool = False,
    silent: bool = False,
    open: bool = False,
):
    """Serve a specific path or the cwd by default. Watch for updates in files in the paths
    provided or in cwd by default. If changes are found then call the appropriate callback and
    reload the page if the callback returns True.
    """

    if version:
        click.echo(f"Livereload v{__version__}")
        exit()

    liveserver = LiveServer(
        watch,
        ignore_list=ignore,
        root=root,
        errors=errors,
        port=port,
        suppress=silent,
        auto_open="" if open else None
    )

    try:
        print(f"Started serving at http://localhost:{port}/")
        liveserver.start()
        while True:
            sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        liveserver.stop()


if __name__ == "__main__":
    serve()
