"""Small, explicit boundaries for filesystem access and subprocesses.

Discovery never creates files. Tests inject every path and the command runner;
there is deliberately no CLI option for redirecting mutation roots.
"""
from __future__ import annotations

import base64
import contextlib
import dataclasses
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time
import uuid


class Error(Exception):
    """A recoverable error that can be shown directly in the panel."""


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(value).hexdigest()


TOOLS = {"systemctl": "/usr/bin/systemctl", "luac": "/usr/bin/luac"}
MAX_STDOUT = 2_000_000
MAX_STDERR = 64_000


@dataclasses.dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


def closed_environment(source=None):
    """Return the small environment needed for user-session discovery."""
    source = os.environ if source is None else source
    keys = ("HOME", "USER", "LOGNAME", "XDG_CONFIG_HOME", "XDG_STATE_HOME",
            "XDG_DATA_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_DIRS", "XDG_RUNTIME_DIR",
            "XDG_CURRENT_DESKTOP", "DBUS_SESSION_BUS_ADDRESS", "LANG", "LC_MESSAGES")
    result = {key: source[key] for key in keys if source.get(key)}
    result.update(LC_ALL="C", SYSTEMD_COLORS="0", PYTHONDONTWRITEBYTECODE="1")
    return result


def bounded_process(argv, *, timeout=15, input=None, env=None,
                    stdout_limit=MAX_STDOUT, stderr_limit=MAX_STDERR,
                    pass_fds=()):
    """Run one absolute command with bounded pipes and process-group cleanup."""
    if not argv or not Path(argv[0]).is_absolute():
        raise Error("External commands must use a trusted absolute path.")
    process = None
    selector = None
    try:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=closed_environment() if env is None else env,
                                   start_new_session=True, pass_fds=tuple(pass_fds))
        input_data = memoryview(input.encode()) if input is not None else None
        if input is not None:
            if len(input_data) > MAX_STDOUT:
                raise Error("External command input exceeded the safety limit.")
        selector = selectors.DefaultSelector()
        buffers = {process.stdout: bytearray(), process.stderr: bytearray()}
        limits = {process.stdout: stdout_limit, process.stderr: stderr_limit}
        for stream in buffers:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        input_offset = 0
        if input_data is not None:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
        deadline = time.monotonic() + timeout
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"exceeded {timeout} seconds")
            for key, _ in selector.select(min(remaining, 0.1)):
                if key.fileobj is process.stdin:
                    try:
                        count = os.write(process.stdin.fileno(), input_data[input_offset:input_offset + 65536])
                    except BrokenPipeError:
                        count = len(input_data) - input_offset
                    input_offset += count
                    if input_offset >= len(input_data):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                    continue
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.fileobj].extend(chunk)
                if len(buffers[key.fileobj]) > limits[key.fileobj]:
                    raise Error("External command output exceeded the safety limit.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"exceeded {timeout} seconds")
        returncode = process.wait(timeout=remaining)
        return ProcessResult(returncode,
                             buffers[process.stdout].decode("utf-8", "replace"),
                             buffers[process.stderr].decode("utf-8", "replace"))
    except (OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
        raise Error(f"Could not run {Path(argv[0]).name}: {exc}") from exc
    finally:
        if process is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            if process.poll() is None:
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
            # The direct command may exit while a detached descendant remains
            # in its process group with inherited streams already closed.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                process.wait()
        if selector is not None:
            selector.close()
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()


def run(argv, *, timeout=15, input=None):
    """Run only the fixed tools used by providers."""
    if not argv or argv[0] not in TOOLS:
        raise Error("Refusing an untrusted external command.")
    trusted = [TOOLS[argv[0]], *argv[1:]]
    result = bounded_process(trusted, timeout=timeout, input=input)
    if result.returncode:
        raise Error((result.stderr.strip() or result.stdout.strip() or
                     f"{argv[0]} exited with {result.returncode}")[:1500])
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
        return path

    @contextlib.contextmanager
    def _target(self, path, *, state=False, create=False):
        """Pin a no-follow parent directory for the lifetime of an operation."""
        path = self.safe_path(path, state=state)
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for component in path.parent.parts[1:]:
                try:
                    next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                                      os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    os.mkdir(component, 0o700, dir_fd=fd)
                    next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                                      os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            yield fd, path.name
        except OSError as exc:
            if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                raise Error(f"Symlinked configuration directories are read-only: {path.parent}") from exc
            raise Error(f"Cannot safely access {path}: {exc}") from exc
        finally:
            os.close(fd)

    @staticmethod
    def _snapshot_at(parent_fd, name):
        try:
            st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return {"type": "absent"}
        if stat.S_ISLNK(st.st_mode):
            return {"type": "link", "target": os.readlink(name, dir_fd=parent_fd)}
        if not stat.S_ISREG(st.st_mode) or st.st_size > 2_000_000:
            raise Error("Refusing a special or oversized configuration file.")
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
        try:
            current = os.fstat(fd)
            if (current.st_dev, current.st_ino) != (st.st_dev, st.st_ino):
                raise Error("Configuration changed while it was being opened.")
            data = bytearray()
            while len(data) <= 2_000_000:
                chunk = os.read(fd, min(65536, 2_000_001 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > 2_000_000:
                raise Error("Refusing an oversized configuration file.")
            return {"type": "file", "data": base64.b64encode(data).decode(),
                    "mode": stat.S_IMODE(current.st_mode)}
        finally:
            os.close(fd)

    def writable(self, path, *, links=False):
        try:
            path = self.safe_path(path)
            if path.is_symlink() and not links:
                return "Symlinked configuration files are read-only."
            probe = path.parent
            while not probe.exists():
                probe = probe.parent
            with self._target(probe / ".omastart-probe") as (fd, _):
                if not os.access(f"/proc/self/fd/{fd}", os.W_OK):
                    return "The configuration directory is not writable."
            return ""
        except (Error, OSError) as exc:
            return str(exc)

    @contextlib.contextmanager
    def locked(self):
        with self._target(self.roots.state / "lock", state=True, create=True) as (parent_fd, name):
            fd = os.open(name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=parent_fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                os.close(fd)

    @staticmethod
    def _replace_at(parent_fd, name, value):
        temporary = ".omastart-" + uuid.uuid4().hex
        if value["type"] == "absent":
            try:
                os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        elif value["type"] == "file":
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent_fd)
            try:
                with os.fdopen(fd, "wb") as stream:
                    os.fchmod(stream.fileno(), value["mode"] & 0o777)
                    stream.write(base64.b64decode(value["data"]))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.rename(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temporary, dir_fd=parent_fd)
        elif value["type"] == "link":
            try:
                os.symlink(value["target"], temporary, dir_fd=parent_fd)
                os.rename(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(temporary, dir_fd=parent_fd)
        else:
            raise Error("Invalid transaction value.")
        os.fsync(parent_fd)

    def _replace(self, path, value, *, state=False):
        with self._target(path, state=state, create=True) as (parent_fd, name):
            self._replace_at(parent_fd, name, value)

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
            if record.get("status") == "committed" and item_id in record.get("sources", {}):
                # Providers need their own history to recognize managed masks
                # and restore exact links after an application-wide change.
                paths = record["sources"][item_id]
                return {**record, "grouped": True,
                        "entries": [entry for entry in record["entries"] if entry["path"] in paths]}
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
        with contextlib.ExitStack() as stack:
            journal_fd, journal_name = stack.enter_context(self._target(path, state=True, create=True))
            targets = [(entry, *stack.enter_context(self._target(Path(entry["path"]), create=True)))
                       for entry in record["entries"]]
            for entry, parent_fd, name in targets:
                if self._snapshot_at(parent_fd, name) not in (entry["before"], entry["after"]):
                    raise Error("Recovery cannot overwrite newer external edits. The original backup is preserved.")
            for entry, parent_fd, name in reversed(targets):
                current = self._snapshot_at(parent_fd, name)
                if current == entry["after"]:
                    self._replace_at(parent_fd, name, entry["before"])
                elif current != entry["before"]:
                    raise Error("The configuration changed during recovery; the backup is preserved.")
            if after:
                after()
            record["status"] = "rolled-back"
            self._replace_at(journal_fd, journal_name,
                             file_value(json.dumps(record, indent=2).encode(), 0o600))

    def transact(self, item_id, changes, *, after=None, sources=None):
        """changes = [(path, expected_snapshot, replacement_snapshot), ...]."""
        if not changes:
            return None
        with contextlib.ExitStack() as stack:
            targets = []
            entries = []
            for path, before, new in changes:
                path = self.safe_path(path)
                parent_fd, name = stack.enter_context(self._target(path, create=True))
                if self._snapshot_at(parent_fd, name) != before:
                    raise Error("Configuration changed outside omastart. Refresh and try again.")
                entry = {"path": str(path), "before": before, "after": new}
                entries.append(entry)
                targets.append((entry, parent_fd, name))
            record = {"version": 1, "item": item_id, "status": "prepared", "entries": entries}
            if sources:
                record["sources"] = sources
            journal = self.roots.state / "transactions" / f"{time.time_ns()}-{uuid.uuid4().hex}.json"
            journal_fd, journal_name = stack.enter_context(self._target(journal, state=True, create=True))
            self._replace_at(journal_fd, journal_name,
                             file_value(json.dumps(record, indent=2).encode(), 0o600))
            applied = []
            try:
                for entry, parent_fd, name in targets:
                    if self._snapshot_at(parent_fd, name) != entry["before"]:
                        raise Error("Configuration changed during the update. Refresh and try again.")
                    self._replace_at(parent_fd, name, entry["after"])
                    applied.append((entry, parent_fd, name))
                if after:
                    after()
                record["status"] = "committed"
                self._replace_at(journal_fd, journal_name,
                                 file_value(json.dumps(record, indent=2).encode(), 0o600))
                return record
            except Exception as exc:
                conflicts = []
                for entry, parent_fd, name in reversed(applied):
                    try:
                        if self._snapshot_at(parent_fd, name) == entry["after"]:
                            self._replace_at(parent_fd, name, entry["before"])
                        else:
                            conflicts.append(entry["path"])
                    except Exception:
                        conflicts.append(entry["path"])
                record.update(status="recovery-required" if conflicts else "rolled-back", error=str(exc))
                self._replace_at(journal_fd, journal_name,
                                 file_value(json.dumps(record, indent=2).encode(), 0o600))
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
