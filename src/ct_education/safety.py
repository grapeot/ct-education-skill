"""Canonical boundaries and descriptor-relative, no-follow file access."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat


REPO = Path(__file__).resolve().parents[2]


class PipelineError(Exception):
    """Only fixed, non-identifying error codes may cross the CLI boundary."""


def disjoint(*paths):
    resolved = [Path(p).expanduser().resolve() for p in paths]
    for index, first in enumerate(resolved):
        for second in resolved[index + 1:]:
            if first == second or first in second.parents or second in first.parents:
                raise PipelineError("E_PATH_OVERLAP")
    return resolved


def boundaries(source=None, workspace=None, annotations=None):
    if not (REPO / "pyproject.toml").is_file() or not (REPO / "src" / "ct_education").is_dir():
        raise PipelineError("E_SOURCE_CHECKOUT_REQUIRED")
    paths = [REPO]
    if source is not None:
        paths.append(source)
    if workspace is not None:
        paths.append(workspace)
    resolved = disjoint(*paths)
    if annotations is not None:
        disjoint(REPO, annotations)
        if workspace is not None:
            disjoint(workspace, annotations)
    return resolved


@contextmanager
def directory_fd(path):
    """Open every canonical path component without following replacement symlinks."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise PipelineError("E_PATH_INVALID")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


@contextmanager
def local_file(root, relative, mode="rb"):
    relative = Path(relative)
    if relative.is_absolute() or any(p in ("..", ".") for p in relative.parts):
        raise PipelineError("E_PATH_INVALID")
    with directory_fd(Path(root) / relative.parent) as parent:
        flags = os.O_RDONLY if mode == "rb" else (os.O_RDWR if "+" in mode else os.O_WRONLY) | os.O_CREAT | os.O_EXCL
        fd = os.open(relative.name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise PipelineError("E_FILE_INVALID")
            stream = os.fdopen(fd, mode)
        except BaseException:
            os.close(fd)
            raise
        with stream:
            yield stream


def write_json(root, relative, value):
    with local_file(root, relative, "wb") as stream:
        stream.write(json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8"))


def read_json(root, relative):
    with local_file(root, relative) as stream:
        content = stream.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            raise PipelineError("E_JSON_SIZE")
        return json.loads(content)
