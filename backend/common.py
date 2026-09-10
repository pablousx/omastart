"""Small, explicit boundaries for filesystem access and subprocesses.

Discovery never creates files. Tests inject every path and the command runner;
there is deliberately no CLI option for redirecting mutation roots.
"""
from __future__ import annotations

import base64
import contextlib
import dataclasses
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import uuid


class Error(Exception):
    """A recoverable error that can be shown directly in the panel."""


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(value).hexdigest()


def run(argv, *, timeout=15, input=None):
    """Never invoke a shell or evaluate startup command strings."""
    try:
        result = subprocess.run(argv, input=input, capture_output=True, text=True,
                                timeout=timeout, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Error(f"Could not run {Path(argv[0]).name}: {exc}") from exc
    if result.returncode:
        raise Error((result.stderr.strip() or result.stdout.strip() or
                     f"{Path(argv[0]).name} exited with {result.returncode}")[:1500])
    return result.stdout


@dataclasses.dataclass(frozen=True)
class Roots:
    home: Path
    config: Path
    state: Path
    config_dirs: tuple[Path, ...]
    data_dirs: tuple[Path, ...]
    unit_dirs: tuple[Path, ...]
    runtime: Path
    desktop: str = "Hyprland"
    language: str = "en_US"

    @classmethod
    def live(cls):
        home = Path.home()

        def envpath(key, default):
            value = Path(os.environ.get(key) or default)
            return value if value.is_absolute() else Path(default)

        def envpaths(key, default):
            return tuple(Path(p) for p in (os.environ.get(key) or default).split(":")
                         if p and Path(p).is_absolute())

        config = envpath("XDG_CONFIG_HOME", home / ".config")
        runtime = envpath("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        configs = envpaths("XDG_CONFIG_DIRS", "/etc/xdg")
        data = (envpath("XDG_DATA_HOME", home / ".local/share"),) + envpaths(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share")
        units = (config / "systemd/user", runtime / "systemd/user", Path("/etc/systemd/user"),
                 Path("/run/systemd/user"), runtime / "systemd/generator",
                 Path("/usr/local/lib/systemd/user"), Path("/usr/lib/systemd/user"),
                 runtime / "systemd/generator.late")
        return cls(home, config, envpath("XDG_STATE_HOME", home / ".local/state") / "omastart",
                   configs, data, units, runtime, os.environ.get("XDG_CURRENT_DESKTOP", "Hyprland"),
                   os.environ.get("LC_MESSAGES") or os.environ.get("LANG", "en_US"))

    @property
    def lua(self):
        return self.config / "hypr/autostart.lua"

    @property
    def autostart(self):
        return self.config / "autostart"

    @property
    def user_units(self):
        return self.config / "systemd/user"


def read_text(path):
    try:
        # Bounded reads: malformed or special files must not hang the shell.
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise Error(f"Not a regular configuration file, or too large: {path}")
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise Error(f"Cannot read {path}: {exc}") from exc


def source(kind, key, name, command, path, enabled, **extra):
    result = dict(id=f"{kind}:{key}", kind=kind, name=name, command=command, path=str(path),
                enabled=enabled, eligible=True, eligibility="", readOnly="", system=False,
                icon="application-x-executable", running="unknown", revision="")
    result.update(extra)
    return result


def snapshot(path):
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {"type": "absent"}
    if stat.S_ISLNK(st.st_mode):
        return {"type": "link", "target": os.readlink(path)}
    if not stat.S_ISREG(st.st_mode) or st.st_size > 2_000_000:
        raise Error(f"Refusing a special or oversized file: {path}")
    return {"type": "file", "data": base64.b64encode(path.read_bytes()).decode(),
            "mode": stat.S_IMODE(st.st_mode)}


def file_value(data, mode=0o644):
    return {"type": "file", "data": base64.b64encode(data).decode(), "mode": mode}


class Store:
    """Durable per-operation journal and compare-before-write recovery.

Only discovered destinations inside the user config are writable. Symlinks
are allowed as *values* for systemd masks/links, never as traversed parents.
"""
    def __init__(self, roots):
        self.roots = roots

    def safe_path(self, path, *, state=False):
        path = Path(os.path.abspath(path))
        base = self.roots.state if state else self.roots.config
        if not base.is_relative_to(self.roots.home):
            raise Error("Configuration and recovery writes must remain inside your home directory.")
        if not path.is_relative_to(base) or path == base:
            raise Error("The destination is outside the per-user configuration directory.")
        # Check ancestors all the way to /, including the configured root.
        for parent in path.parents:
            if parent.is_symlink():
                raise Error(f"Symlinked configuration directories are read-only: {parent}")
        return path

    def writable(self, path, *, links=False):
        try:
            path = self.safe_path(path)
            if path.is_symlink() and not links:
                return "Symlinked configuration files are read-only."
            parent = path.parent
            while not parent.exists():
                parent = parent.parent
            if not os.access(parent, os.W_OK):
                return "The configuration directory is not writable."
            return ""
        except Error as exc:
            return str(exc)

    @contextlib.contextmanager
    def locked(self):
        self.safe_path(self.roots.state / "lock", state=True)
        self.roots.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.roots.state / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _replace(self, path, value, *, state=False):
        path = self.safe_path(path, state=state)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if value["type"] == "absent":
            path.unlink(missing_ok=True)
        elif value["type"] == "file":
            fd, temporary = tempfile.mkstemp(prefix=".omastart-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    os.fchmod(stream.fileno(), value["mode"] & 0o777)
                    stream.write(base64.b64decode(value["data"]))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.lexists(temporary):
                    os.unlink(temporary)
        elif value["type"] == "link":
            temporary = path.parent / (".omastart-" + uuid.uuid4().hex)
            try:
                os.symlink(value["target"], temporary)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            raise Error("Invalid transaction value.")
        fd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def journal_write(self, path, record):
        self._replace(path, file_value(json.dumps(record, indent=2).encode(), 0o600), state=True)

    def previous(self, item_id):
        folder = self.roots.state / "transactions"
        if not folder.is_dir():
            return None
        for path in sorted(folder.glob("*.json"), reverse=True):
            try:
                record = json.loads(read_text(path))
            except (Error, ValueError):
                continue
            if record.get("item") == item_id and record.get("status") == "committed":
                return record
        return None

    def pending(self):
        folder = self.roots.state / "transactions"
        records = []
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                try:
                    record = json.loads(read_text(path))
                    if record.get("status") in ("prepared", "recovery-required"):
                        records.append((path, record))
                except (Error, ValueError):
                    continue
        return records

    def recover(self, path, record, *, after=None):
        """Resume rollback of a prepared transaction without clobbering edits."""
        for entry in record["entries"]:
            destination = self.safe_path(Path(entry["path"]))
            if snapshot(destination) not in (entry["before"], entry["after"]):
                raise Error("Recovery cannot overwrite newer external edits. The original backup is preserved.")
        for entry in reversed(record["entries"]):
            destination = Path(entry["path"])
            current = snapshot(destination)
            if current == entry["after"]:
                self._replace(destination, entry["before"])
            elif current != entry["before"]:
                raise Error("The configuration changed during recovery; the backup is preserved.")
        if after:
            after()
        record["status"] = "rolled-back"
        self.journal_write(path, record)

    def transact(self, item_id, changes, *, after=None):
        """changes = [(path, expected_snapshot, replacement_snapshot), ...]."""
        entries = []
        for path, before, new in changes:
            path = self.safe_path(path)
            if snapshot(path) != before:
                raise Error("Configuration changed outside omastart. Refresh and try again.")
            entries.append({"path": str(path), "before": before, "after": new})
        if not entries:
            return None
        record = {"version": 1, "item": item_id, "status": "prepared", "entries": entries}
        journal = self.roots.state / "transactions" / f"{time.time_ns()}-{uuid.uuid4().hex}.json"
        self.journal_write(journal, record)
        applied = []
        try:
            for entry in entries:
                path = Path(entry["path"])
                if snapshot(path) != entry["before"]:
                    raise Error("Configuration changed during the update. Refresh and try again.")
                self._replace(path, entry["after"])
                applied.append(entry)
            if after:
                after()
            record["status"] = "committed"
            self.journal_write(journal, record)
            return record
        except Exception as exc:
            conflicts = []
            for entry in reversed(applied):
                path = Path(entry["path"])
                try:
                    if snapshot(path) == entry["after"]:
                        self._replace(path, entry["before"])
                    else:
                        conflicts.append(str(path))
                except Exception:
                    conflicts.append(str(path))
            record.update(status="recovery-required" if conflicts else "rolled-back", error=str(exc))
            self.journal_write(journal, record)
            if after:
                with contextlib.suppress(Exception):
                    after()
            detail = " External changes were preserved; see the recovery journal." if conflicts else " Changes were rolled back."
            raise Error(str(exc) + detail) from exc

    def undo_changes(self, record):
        if not record:
            raise Error("There is no omastart change to restore.")
        changes = []
        for entry in record["entries"]:
            path = self.safe_path(Path(entry["path"]))
            if snapshot(path) != entry["after"]:
                raise Error("This configuration changed externally. Refresh; the backup was preserved.")
            changes.append((path, entry["after"], entry["before"]))
        return changes
