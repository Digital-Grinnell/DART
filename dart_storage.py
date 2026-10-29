"""Fail-closed storage for the optional POSIX managed service."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MARKER = ".dart-storage"
MARKER_VALUE = "DART managed storage v1\n"
DEFAULT_MIN_FREE_BYTES = 50 * 1024**3


class LowDiskSpace(RuntimeError):
    """Work must stop, but reserved space remains available for evidence."""


def private(path: Path, *, directory: bool = False) -> None:
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError(f"Owner-only permissions and current-user ownership required: {path}")
    if directory and not path.is_dir():
        raise ValueError(f"Not a directory: {path}")
    if not directory and (not path.is_file() or path.is_symlink()):
        raise ValueError(f"Not a regular private file: {path}")


def absolute(raw: str) -> Path:
    if not raw or not Path(raw).is_absolute() or raw.startswith(("/Volumes/", "//")):
        raise ValueError("Enter an absolute Linux server path, not a Mac /Volumes or UNC path.")
    return Path(raw).resolve(strict=True)


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode())


def atomic_bytes(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_environment(raw: str) -> None:
    from dotenv import dotenv_values

    path = absolute(raw)
    private(path)
    values = dotenv_values(path, interpolate=False)
    allowed = {"DART_CONFIG_DIR", "DART_DATA_DIR", "DART_SOURCE_ROOTS", "DART_AZURE_CONNECTION_STRING"}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError("Unknown environment-file setting names; consult dart.env.example.")
    # The selected file is authoritative; inherited credentials cannot enable uploads.
    for key in allowed:
        os.environ.pop(key, None)
    for key, value in values.items():
        if value is None:
            raise ValueError(f"Missing value for {key} in private environment file.")
        os.environ[key] = value


def redact(message: object) -> str:
    text = str(message)
    for name, value in os.environ.items():
        if value and any(word in name.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "CONNECTION_STRING", "API_KEY")):
            text = text.replace(value, "[redacted]")
    text = re.sub(r"(?i)(AccountKey|SharedAccessSignature|sig|password|token)\s*=\s*[^;\s&]+",
                  r"\1=[redacted]", text)
    text = re.sub(r"(https?://[^\s?\"'<>]+)\?[^\s\"'<>]+", r"\1?[redacted]", text)
    return text


@dataclass
class Storage:
    config: Path
    data: Path
    sources: tuple[tuple[Path, Path], ...] = ()
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES
    _identities: dict[Path, tuple[int, int]] = field(default_factory=dict, init=False)

    @classmethod
    def from_environment(cls) -> Storage:
        roots = [absolute(os.environ.get(name, "")) for name in ("DART_CONFIG_DIR", "DART_DATA_DIR")]
        for root in roots:
            private(root, directory=True)
        if roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0]):
            raise ValueError("Configuration and data roots must be separate, non-nested directories.")
        sources = []
        values = json.loads(os.environ.get("DART_SOURCE_ROOTS", "[]"))
        if not isinstance(values, list):
            raise ValueError("DART_SOURCE_ROOTS must be a JSON list of path/mount objects.")
        for value in values:
            if not isinstance(value, dict) or set(value) != {"path", "mount"}:
                raise ValueError("Each approved source requires exactly path and mount.")
            path, mount = absolute(value["path"]), absolute(value["mount"])
            if not path.is_dir() or not os.path.ismount(mount) or not path.is_relative_to(mount):
                raise ValueError(f"Source must be under a verified mounted filesystem: {path}")
            if any(path.is_relative_to(root) or root.is_relative_to(path) for root in roots):
                raise ValueError("External source roots must not overlap DART managed roots.")
            sources.append((path, mount))
        return cls(*roots, tuple(sources))

    @property
    def projects(self) -> Path:
        return self.data / "projects"

    @property
    def jobs(self) -> Path:
        return self.data / "jobs"

    def initialize(self) -> None:
        """Explicit initialization of existing approved roots, never a startup fallback."""
        for root in (self.config, self.data):
            private(root, directory=True)
            marker = root / MARKER
            if not marker.exists():
                descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as handle:
                    handle.write(MARKER_VALUE)
                    handle.flush()
                    os.fsync(handle.fileno())
        for path in (self.projects, self.jobs):
            path.mkdir(mode=0o700, exist_ok=True)
            private(path, directory=True)
        self.check()

    def check(self) -> None:
        for root in (self.config, self.data):
            private(root, directory=True)
            marker = root / MARKER
            private(marker)
            if marker.read_text() != MARKER_VALUE:
                raise ValueError(f"Invalid DART storage marker: {marker}")
            info = root.stat()
            identity = (info.st_dev, info.st_ino)
            if self._identities.setdefault(root, identity) != identity:
                raise OSError(f"Storage identity changed; stop and inspect before restarting: {root}")
            with tempfile.TemporaryFile(dir=root) as handle:
                handle.write(b"DART storage check\n")
                handle.flush()
                os.fsync(handle.fileno())
        for root in (self.projects, self.jobs):
            private(root, directory=True)
            if root.is_symlink():
                raise ValueError(f"Managed directories must not be symlinks: {root}")
        for path, mount in self.sources:
            if not os.path.ismount(mount) or not path.is_dir():
                raise OSError(f"Approved source mount is unavailable: {mount}")
            info = mount.stat()
            identity = (info.st_dev, info.st_ino)
            if self._identities.setdefault(mount, identity) != identity:
                raise OSError(f"Source mount identity changed: {mount}")
            info = path.stat()
            identity = (info.st_dev, info.st_ino)
            if self._identities.setdefault(path, identity) != identity:
                raise OSError(f"Approved source root identity changed: {path}")

    def require_space(self, *, additional_bytes: int = 0) -> None:
        for root in (self.config, self.data):
            free = shutil.disk_usage(root).free
            required = self.min_free_bytes + additional_bytes
            if free < required:
                raise LowDiskSpace(
                    f"Low disk space at {root}: {free} bytes free; require {required} bytes "
                    f"({self.min_free_bytes} reserve + {additional_bytes} operation headroom). "
                    "Work stopped; retain partial outputs and reclaim verified files before retrying.")

    def managed(self, raw: str, *, directory: bool = False) -> Path:
        self.check()
        path = absolute(raw)
        if not path.is_relative_to(self.projects) or path == self.projects:
            raise ValueError(f"Project paths must be below {self.projects}")
        if directory and not path.is_dir():
            raise ValueError(f"Not a project directory: {path}")
        if not directory and not path.is_file():
            raise ValueError(f"Not a project file: {path}")
        if path.is_dir():
            private(path, directory=True)
        else:
            private(path)
        return path

    def source(self, raw: str, *, directory: bool = False) -> Path:
        self.check()
        path = absolute(raw)
        if path != Path(raw):
            raise ValueError("Source aliases must be reviewed explicitly; use the approved canonical server path.")
        if not any(path.is_relative_to(root) for root in (self.projects, *(p for p, _ in self.sources))):
            raise ValueError("Source must be inside a DART project or an explicitly approved source mount.")
        if not (path.is_dir() if directory else path.is_file()):
            raise ValueError(f"Unavailable source {'directory' if directory else 'file'}: {path}")
        if directory:
            with os.scandir(path) as entries:
                next(entries, None)
        else:
            with path.open("rb") as handle:
                handle.read(1)
        return path

    def working(self, raw: str) -> Path:
        path = self.managed(raw, directory=True)
        hidden = path / ".DART-working-directory"
        if hidden.exists() or hidden.is_symlink():
            if hidden.is_symlink():
                raise ValueError("The DART working directory must not be a symlink.")
            private(hidden, directory=True)
        return path
