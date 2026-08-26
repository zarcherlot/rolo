from __future__ import annotations

import errno
import hashlib
import json
import os
import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


def _process_exists(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        open_process.restype = ctypes.c_void_p
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        handle = open_process(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            close_handle(handle)
            return True
        return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER means no PID.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno != errno.ESRCH
    return True


def _same_host_lock_owner_is_dead(lock_path: Path) -> bool:
    """Reclaim only a lock whose recorded process is gone on this exact host."""
    try:
        if lock_path.stat().st_size > 4096:
            return False
        owner = json.loads(lock_path.read_text(encoding="ascii"))
        if owner.get("host") != socket.gethostname():
            return False
        pid = owner.get("pid")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return False
        return not _process_exists(pid)
    except FileNotFoundError:
        return False
    except (json.JSONDecodeError, OSError):
        return False


def _unlink_lock_with_bounded_retry(lock_path: Path) -> bool:
    deadline = time.monotonic() + 0.5
    delay_s = 0.005
    while True:
        try:
            lock_path.unlink()
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if os.name != "nt" or time.monotonic() >= deadline:
                return False
            time.sleep(delay_s)
            delay_s = min(delay_s * 2, 0.05)


@contextmanager
def interprocess_lock(
    target: Path, *, timeout_s: float = 10.0, stale_after_s: float = 120.0
) -> Iterator[None]:
    """Serialize writers with a bounded, crash-recoverable sibling lock file."""
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_id = hashlib.sha256(target.name.encode("utf-8")).hexdigest()[:8]
    lock_path = target.with_name(f".l{lock_id}")
    deadline = time.monotonic() + timeout_s
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(
                descriptor,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                        "created_at": time.time(),
                    }
                ).encode("ascii"),
            )
            os.fsync(descriptor)
        except (FileExistsError, PermissionError) as exc:
            # Windows may report a sharing violation as PermissionError while another process
            # owns the lock file. The owner may remove it before exists()/stat(), so a missing
            # path is also retried within the same bounded deadline instead of being mistaken
            # for a permanent ACL failure.
            if isinstance(exc, PermissionError) and not lock_path.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"timed out waiting for artifact lock: {target}"
                    ) from None
                time.sleep(0.02)
                continue
            try:
                stale = time.time() - lock_path.stat().st_mtime > stale_after_s
            except FileNotFoundError:
                continue
            if stale or _same_host_lock_owner_is_dead(lock_path):
                if _unlink_lock_with_bounded_retry(lock_path):
                    continue
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for artifact lock: {target}"
                ) from None
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(descriptor)
        if not _unlink_lock_with_bounded_retry(lock_path):
            lock_path.unlink()


def atomic_write_text(
    path: Path,
    value: str,
    *,
    acquire_lock: bool = True,
    require_absent: bool = False,
) -> None:
    """Durably replace one file through a unique same-directory temporary."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    def replace_with_bounded_retry(source: Path, destination: Path) -> None:
        deadline = time.monotonic() + 0.5
        delay_s = 0.01
        while True:
            try:
                os.replace(source, destination)
                return
            except PermissionError:
                # Windows file-system filters can briefly retain a just-closed file handle.
                # The sibling lock still owns writer serialization, so retrying this exact
                # atomic replacement cannot interleave another writer.
                if os.name != "nt" or time.monotonic() >= deadline:
                    raise
                time.sleep(delay_s)
                delay_s = min(delay_s * 2, 0.05)

    def write() -> None:
        if require_absent and path.exists():
            raise FileExistsError(path)
        # Keep the sibling name short enough for Windows MAX_PATH while retaining 48 bits of
        # per-write uniqueness. The exclusive create still detects the improbable collision.
        temporary = path.with_name(f".t{uuid4().hex[:12]}")
        try:
            with temporary.open("x", encoding="utf-8", newline="") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            replace_with_bounded_retry(temporary, path)
            if os.name != "nt":
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    if acquire_lock:
        with interprocess_lock(path):
            write()
    else:
        write()


def append_text_record(path: Path, record: str) -> None:
    """Append exactly one durable record without cross-process interleaving."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with interprocess_lock(path):
        with path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(record)
            stream.flush()
            os.fsync(stream.fileno())
