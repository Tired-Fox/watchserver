#!/usr/bin/env python
from __future__ import annotations

from time import sleep
import click

from liveserver import __version__, LiveServer

HELP = {
    "root": "path where the server should attach",
    "base": "base path where the server will find custom error files.",
    "serve": "port that the server will serve to",
    "watch": "list of paths to watch. Repeat the command for each entry to the list",
    "version": "Version of mophidian",
    "silent": "Surpress all logs from the server and file watcher",
    "open": "Toggle on auto open. This will automatically open the base url in the browser."
}

@click.option("-r", "--root", default="", help=HELP["root"])
@click.option("-b", "--base", default="", help=HELP["base"])
@click.option("-p", "--port", default=3031, help=HELP["serve"])
@click.option("-w", "--watch", multiple=True, default=[], help=HELP["watch"])
@click.option("-v", "--version", flag_value=True, default=False, help=HELP["version"])
@click.option("-o", "--open", flag_value=True, default=False, help=HELP["open"])
@click.option("-s", "--silent", flag_value=True, default=False, help=HELP["silent"])
@click.command(name="serve")
def serve(
    root: str="",
    base: str = "",
    port: int=3031,
    watch: list[str]=[],
    version: bool = False,
    silent: bool = False,
    open: bool = False,
):
    """ Serve a specific path or the cwd by default. Watch for updates in files in the paths
    provided or in cwd by default. If changes are found then call the appropriate callback and
    reload the page if the callback returns True.
    """

    if version:
        click.echo(f"Livereload v{__version__}")
        exit()

    liveserver = LiveServer(
        *watch,
        root=root,
        base=base,
        port=port,
        suppress=silent,
        auto_open=open
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
