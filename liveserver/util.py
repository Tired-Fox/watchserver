from __future__ import annotations
from functools import cached_property

import os
from pathlib import Path
import platform
from typing import Literal
import string

LOCALHOST: tuple[Literal['127.0.0.1', 'localhost']] = ("127.0.0.1", "localhost")
SERVER_PORT = 3031
PORT_RANGE = [49200, 65535]

PLATFORM = platform.system()

livereload_script = string.Template(
    """
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
                console.warn("[Live Reload] Detached: Server closed");
            }
        };
        req.open("GET", '/livereload/${path}');
        req.send();
    }
    livereload();
    console.warn("[Live Reload] Attached: '${path}'");
</script>
"""
)

def path_exists_case_sensitive(p: str|Path) -> bool:
    """Check if path exists, enforce case sensitivity.

    Arguments:
      p: Path to check
    Returns:
      Boolean indicating if the path exists or not
    """
    p = Path(p)
    # If it doesn't exist initially, return False
    if not p.exists():
        return False

    # Else loop over the path, checking each consecutive folder for
    # case sensitivity
    while True:
        # At root, p == p.parent --> break loop and return True
        if p == p.parent:
            return True
        # If string representation of path is not in parent directory, return False
        if str(p) not in map(str, p.parent.iterdir()):
            return False
        p = p.parent


def default(root: str, src: str) -> list[str]:
    if src.endswith((".css", ".js")):
        return [translate_path(root, src), "**"]
    return [translate_path(root, src)]

def translate_path(root, src) -> str:
    path =  ServerPath(src).lstrip().lstrip(root)
    
    if len(path.parents) == 0:
        return "/"
    if path.isfile():
        path = path.parent.normpath()
        return path.posix() + "/"
    path = path.normpath()
    return path.posix() + "/"

class ServerPath:
    """Path object for the live reload server. Keeps the seperators as `/` and does a lot of extra
    work for normalizing the path. It also has a case sensitive check for if the path exists. This
    is needed for windows systems.
    """

    def __init__(self, *paths: str) -> None:
        flat = []
        for p in paths:
            if isinstance(p, (list, set, tuple)):
                flat.extend(p)
            else:
                flat.append(p)

        self.path = "/".join(str(p) for p in flat if p != "").replace("\\", "/").replace("//", "/")
        if len(self.path) > 2:
            self.path = self.path.replace("./", "")

    @property
    def parent(self) -> ServerPath:
        """Return a new ServerPath instance that represents the parent directory."""
        parts = self.path.rsplit("/", 1)
        if len(parts) > 1:
            if parts[0] != "":
                return ServerPath(parts[0], "/")
            return ServerPath(parts[0])
        else:
            return ServerPath("")

    @property
    def parents(self) -> list[str]:
        """Return a list of all the parent directories."""
        return self.path.split("/")[:-1]

    @cached_property
    def name(self) -> str:
        """Name of the file/directory path. This is the last named segement of the path."""
        return self.path.rsplit("/", 1)[-1].split(".", 1)[0]

    @cached_property
    def suffix(self) -> str:
        """Suffix of the file path. None if no file extension is found."""
        parts = self.path.rsplit("/", 1)[-1].split(".", 1)
        if len(parts) > 1:
            return f".{parts[-1]}"
        else:
            return None

    def with_suffix(self, suffix: str = ""):
        """Replace the file paths suffix. Either an extension or blank for removing the extension.
        """
        suffix = f".{suffix}" if not suffix.startswith(".") and suffix != "" else suffix
        parts = self.path.rsplit("/", 1)
        if len(parts) > 1:
            self.path = parts[0] + "/" + self.name.split(".", 1)[0] + suffix
        else:
            self.path = parts[0].split(".", 1)[0] + suffix
        return self

    def with_name(self, name: str):
        """Replace the paths name. Either the file path name or the directory name."""
        trail = "/" if self.path.endswith("/") else ""
        parts = self.path.rstrip("/").rsplit("/", 1)

        suffix_parts = parts[-1].split(".", 1)
        suffix = f".{suffix_parts[-1]}" if len(suffix_parts) > 1 else ""

        if len(parts) > 1:
            self.path = parts[0] + "/" + name + suffix + trail
        else:
            self.path = name + suffix + trail
        return self

    def relative_to(self, rel_path: str) -> ServerPath:
        """Calculate the path to the relative path assuming that the current paths root is the
        current directory.
        """
        parents = self.parents

        rel_path = rel_path.replace("\\", "/").replace("//", "/").split("/")
        parent_pos = len(parents)
        for i, part in enumerate(rel_path):
            if part == "..":
                parent_pos -= 1
                if parent_pos < 0:
                    raise IndexError(f"Can't have a relative path that is outside the outer most\
scope of the current path {self.posix()!r}")
            else:
                return ServerPath(*parents[:parent_pos], *rel_path[i:])
        return ServerPath(*parents[:parent_pos])

    def regex(self) -> str:
        """Replace ** with .* and * with [^/]* in the path."""
        parts = []
        for part in self.path.split("/"):
            if part == "**":
                parts.append(".*")
            else:
                parts.append(part.replace("*", "[^/]*"))
        return "/".join(parts)
    
    def strip(self, text: str = "/"):
        """Remove a substring from the start and end of the path."""
        self.path = self.path.strip(text)
        return self

    def rstrip(self, end: str = "/"):
        """Remove a substring from the end of the path."""
        self.path = self.path.rstrip(end)
        return self

    def lstrip(self, start: str = "/"):
        """Remove a substring from the start of the path."""
        self.path = self.path.lstrip(start)
        return self

    def normpath(self):
        """Remove leading and trailing `/` and replace all double slashes with single slashes."""
        self.path = self.path.strip("/").replace("//", "/")
        return self

    def join(self, *paths) -> ServerPath:
        """Return a new ServerPath instance with the current path joined with the passed in paths.
        """
        return ServerPath(self.path, *paths)

    def exists(self) -> bool:
        """Check if the path exists. Either file or directory."""
        return path_exists_case_sensitive(self.path)

    def isdir(self) -> bool:
        """Check if the path is a directory. Ignores if it exists."""
        return os.path.isdir(self.path) and self.exists()

    def isfile(self) -> bool:
        """Check if the path is a file. Ignores if it exists."""
        return os.path.isfile(self.path) and self.exists()

    def posix(self) -> str:
        """Get the string representation of the path."""
        return self.path if self.path != "" else "."

    def win(self) -> str:
        """Get the windows representation of the path."""
        return self.path.replace("/", "\\") if self.path != "" else "."

    def platform(self) -> str:
        """Returns the stringified version of the path with the seperators that match the current
        operating system.
        """
        if PLATFORM == "Windows":
            return self.win()
        return self.posix()

    def __repr__(self) -> str:
        return f"ServerPath({self.path!r})"

    def __str__(self) -> str:
        return self.path

if __name__ == "__main__":
    print(ServerPath("*/**/rainbow").regex())
    print(Path("Server.py").exists())
