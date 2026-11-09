"""Strict portable records and confined filesystem primitives for transcript banks."""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import uuid
from pathlib import Path, PurePosixPath

if os.name != 'nt':
    import fcntl

try:
    from .platform_fs import is_link_or_reparse
except ImportError:  # pragma: no cover - engine core module not yet present
    def is_link_or_reparse(path):
        """Dev fallback mirroring engine core platform_fs.is_link_or_reparse."""
        import stat
        path = Path(path)
        if path.is_symlink():
            return True
        if os.name == 'nt':
            try:
                return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            except FileNotFoundError:
                pass
        return False

from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = Path(__file__).resolve().parents[1] / "data" / "modelo" / "transcripciones"
PRODUCER_VERSION = "transcripciones-1.0"


class ModelError(ValueError):
    """Machine-readable failure; messages deliberately avoid source contents."""
    def __init__(self, code, message="Invalid transcript record"):
        self.code = code
        super().__init__(f"{code}: {message}")


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ModelError("UNSAFE_ID")
    return value


def _parts(relative):
    value = str(relative)
    parts = value.split("/")
    if not value or PurePosixPath(value).is_absolute() or any(p in ("", ".", "..") for p in parts) or "\\" in value or ":" in value or "\x00" in value:
        raise ModelError("UNSAFE_PATH")
    return parts


def safe_path(root, relative):
    """Validate without resolving away symlinks. IO helpers also use dir_fd/O_NOFOLLOW."""
    path = Path(os.path.abspath(root))
    for candidate in [*reversed(path.parents), path]:
        if is_link_or_reparse(candidate):
            raise ModelError("UNSAFE_PATH")
    for part in _parts(relative):
        path = path / part
        if is_link_or_reparse(path):
            raise ModelError("UNSAFE_PATH")
    return path


def validate_bank_location(bank, vault=None):
    """Keep private banks outside Git worktrees and known Obsidian vaults.

    No directory is created. Inspect Git from the nearest existing parent, so
    a new child of a repository cannot bypass the check. An explicit vault is
    useful before its .obsidian marker exists.
    """
    path = Path(os.path.abspath(bank))
    safe_path(path, ".location-check")
    if vault is not None:
        vault_path = Path(os.path.abspath(vault))
        if path == vault_path or vault_path in path.parents:
            raise ModelError("BANK_INSIDE_VAULT")
    for candidate in (path, *path.parents):
        marker = candidate / ".obsidian"
        if marker.exists() or marker.is_symlink():
            raise ModelError("BANK_INSIDE_VAULT")
        git_marker = candidate / ".git"
        if git_marker.exists() or git_marker.is_symlink():
            raise ModelError("BANK_INSIDE_GIT")
    existing = path
    while not existing.exists():
        existing = existing.parent
    if not existing.is_dir():
        raise ModelError("UNSAFE_PATH")
    # Ambient GIT_DIR/WORK_TREE would otherwise change what repository is tested.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["LC_ALL"] = "C"
    try:
        probe = subprocess.run(["git", "-C", str(existing), "rev-parse", "--is-inside-work-tree"],
                               env=environment, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ModelError("BANK_LOCATION_UNVERIFIED") from exc
    if probe.returncode == 0 and probe.stdout.strip() == "true":
        raise ModelError("BANK_INSIDE_GIT")
    if probe.returncode not in (0, 128):
        raise ModelError("BANK_LOCATION_UNVERIFIED")
    if probe.returncode == 128 and "not a git repository" not in probe.stderr.lower():
        raise ModelError("BANK_LOCATION_UNVERIFIED")
    # A bare repository is also a product repository, not a private bank.
    if probe.returncode == 0:
        raise ModelError("BANK_INSIDE_GIT")
    return path


@contextlib.contextmanager
def _directory(path, create=False):
    absolute = Path(os.path.abspath(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in absolute.parts[1:]:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except OSError as exc:
                raise ModelError("UNSAFE_PATH", "Directory missing or not a real directory") from exc
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_bytes(root, relative):
    if os.name == 'nt':
        from .windows_fs import read_bytes as native_read_bytes
        return native_read_bytes(root, relative)
    path = safe_path(root, relative)
    with _directory(path.parent) as parent:
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        except OSError as exc:
            raise ModelError("UNSAFE_PATH", "Cannot read regular file") from exc
        try:
            import stat
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ModelError("UNSAFE_PATH", "Not a regular file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                return stream.read()
        finally:
            os.close(fd)


def load_json(path):
    path = Path(path)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ModelError("INVALID_JSON", "Duplicate object key")
            result[key] = value
        return result
    try:
        return json.loads(read_bytes(path.parent, path.name), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ModelError("INVALID_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModelError("INVALID_JSON") from exc


def atomic_write(root, relative, data, *, immutable=True):
    if os.name == 'nt':
        from .windows_fs import atomic_write as native_atomic_write
        return native_atomic_write(root, relative, data, immutable=immutable)
    path = safe_path(root, relative)
    with _directory(path.parent, create=True) as parent:
        name = f".tmp-{uuid.uuid4().hex}"
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if immutable:
                try:
                    os.link(name, path.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                except FileExistsError:
                    if read_bytes(root, relative) != data:
                        raise ModelError("IMMUTABLE_CONFLICT")
            else:
                safe_path(root, relative)
                os.replace(name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(name, dir_fd=parent)
            except FileNotFoundError:
                pass


@contextlib.contextmanager
def bank_lock(bank):
    """One OS lock shared by every consolidator; released automatically on process death."""
    from .transcripciones_lectura import live_reads
    validate_bank_location(bank)
    if os.name == 'nt':
        from .windows_fs import ensure_private_directory, file_lock
        ensure_private_directory(bank)
        with live_reads(), file_lock(Path(bank) / '.writer.lock'):
            yield
        return
    with live_reads(), _directory(bank, create=True) as parent:
        fd = os.open(".writer.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def validate_record(kind, record, resolver=None):
    if not re.fullmatch(r"[a-z][a-z0-9-]*", kind):
        raise ModelError("SCHEMA_UNKNOWN")
    schema_path = SCHEMAS / f"{kind}.schema.json"
    if not schema_path.is_file():
        raise ModelError("SCHEMA_UNKNOWN")
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding='utf-8')), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda e: str(list(e.path)))
    if errors:
        # Schema errors often interpolate private values: expose only structural location.
        raise ModelError("SCHEMA_INVALID", "/".join(map(str, errors[0].path)) or kind)
    if kind == "capture-manifest":
        if record["completeness"] == "complete" and (not all(record["evidence"][k].strip() for k in ("beginning", "ending", "continuity")) or record["evidence"]["gaps"]):
            raise ModelError("COMPLETENESS_UNPROVEN")
        if record["file"] is None and record["completeness"] != "inaccessible":
            raise ModelError("INPUT_EMPTY")
        if record["completeness"] == "inaccessible" and (record["file"] is not None or not (record["evidence"]["gaps"] or record["evidence"]["uncertainties"])):
            raise ModelError("ACCESS_EVIDENCE_MISSING")
        if record["file"]:
            _parts(record["file"]["path"])
    if kind == "original":
        _parts(record["blob_path"])
        if record["blob_path"] != f"originales/{record['sha256']}.bin":
            raise ModelError("BLOB_REFERENCE_INVALID")
        if record["version_id"] == record["previous_version_id"]:
            raise ModelError("VERSION_CYCLE")
        if resolver is not None:
            data = resolver(record["blob_path"])
            if len(data) != record["byte_length"] or sha256_bytes(data) != record["sha256"]:
                raise ModelError("HASH_MISMATCH")
    if kind == "catalogo" and record["preferred_version_id"] not in [None, *record["version_ids"]]:
        raise ModelError("VERSION_REFERENCE_INVALID")
    return {"valid": True, "kind": kind}


def result(operation, *, request_id="local", status="DONE", input_hashes=None, outputs=None, warnings=None, evidence=None):
    return {"schema_version": "resultado.v1", "operation": operation, "request_id": request_id,
            "status": status, "input_hashes": input_hashes or [], "outputs": outputs or [],
            "warnings": warnings or [], "errors": [], "next_action": None, "evidence": evidence or {}}
