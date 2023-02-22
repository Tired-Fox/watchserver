#!/usr/bin/env python
from __future__ import annotations

from time import sleep
import click

from liveserver import __version__, LiveServer

@click.option("-r", "--root", default="", help="path where the server should attach")
@click.option("-p", "--port", default=3031, help="port to serve to")
@click.option(
    "-w",
    "--watch",
    multiple=True,
    default=[],
    help="list of paths to watch for changes. This must be in the format of a python list with \
only strings inside. Ex. ['blog/python/']"
)
@click.option("-v", "--version", flag_value=True, help="Version of mophidian", default=False)
@click.command(name="serve")
def serve(root: str="", port: int=3031, watch: list[str]=[], version: bool = False):
    """Serve a specific path or the cwd by default. Watch for updates in files in the paths provided
    or in cwd by default. If changes are found then call the appropriate callback and reload the page
    if the callback returns True.
    """

    if version:
        click.echo(f"Livereload v{__version__}")
        exit()

    liveserver = LiveServer(*watch, port=port)
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
