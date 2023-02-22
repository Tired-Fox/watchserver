#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path
from time import sleep
import click
import ast

from . import __version__, LiveServer


class PythonList(click.Option):

    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except:
            raise click.BadParameter(value)

@click.group(invoke_without_command=True)
@click.option("-v", "--version", flag_value=True, help="Version of mophidian", default=False)
def cli(version: bool = False):
    '''Pythonic Static Site Generator CLI.'''

    if version:
        click.echo(f"Livereload v{__version__}")
        exit()

@cli.command(name="serve")
@click.option("-r", "--root", default="", help="path where the server should attach")
@click.option("-p", "--port", default=8080, help="port to serve to")
@click.option(
    "-w",
    "--watch",
    cls=PythonList,
    default=[],
    help="list of paths to watch for changes. This must be in the format of a python list with \
only strings inside. Ex. ['blog/python/']"
)
def serve(root: str, port: int, watch: list[str]):
    """Serve a specific path or the cwd by default. Watch for updates in files in the paths provided
    or in cwd by default. If changes are found then call the appropriate callback and reload the page
    if the callback returns True.
    """

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
    cli()
