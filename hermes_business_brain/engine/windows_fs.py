"""Native Windows confined I/O (local NTFS/ReFS only).

Every ancestor stays open without delete sharing throughout an operation. Reparse
points are rejected, including junctions. File data is flushed before publication;
Win32 has no unprivileged directory-fsync equivalent, so power-loss persistence of
the directory entry is not promised. This module is importable on POSIX, but its
operations require Windows. Administrative principals remain trusted, as root does
on POSIX. Existing ACLs are inspected, never silently repaired.
"""
from __future__ import annotations

import contextlib
import ctypes as C
import os
import re
import uuid
from ctypes import wintypes as W
from pathlib import Path


def _error(code="UNSAFE_PATH"):
    from . import transcripciones_modelo
    return transcripciones_modelo.ModelError(code)


def _api():
    if os.name != "nt":
        raise OSError("Native Windows backend requires Windows")
    return _K, _A


class _SA(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class _Info(C.Structure):
    _fields_ = [("attributes", W.DWORD), ("creation", W.FILETIME),
                ("access", W.FILETIME), ("write", W.FILETIME),
                ("volume", W.DWORD), ("size_high", W.DWORD),
                ("size_low", W.DWORD), ("links", W.DWORD),
                ("index_high", W.DWORD), ("index_low", W.DWORD)]


class _Overlapped(C.Structure):
    _fields_ = [("internal", C.c_size_t), ("internal_high", C.c_size_t),
                ("offset", W.DWORD), ("offset_high", W.DWORD), ("event", W.HANDLE)]


class _RenameInfo(C.Structure):
    _fields_ = [("replace", W.DWORD), ("root", W.HANDLE),
                ("length", W.DWORD), ("name", W.WCHAR * 1)]


if os.name == "nt":
    _K = C.WinDLL("kernel32", use_last_error=True)
    _A = C.WinDLL("advapi32", use_last_error=True)
    def _bind(lib, name, args, result=W.BOOL):
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = args, result
    P = C.c_void_p
    _bind(_K, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, P, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
    _bind(_K, "CloseHandle", [W.HANDLE])
    _bind(_K, "GetCurrentProcess", [], W.HANDLE)
    _bind(_K, "LocalFree", [P], P)
    _bind(_K, "GetFileInformationByHandle", [W.HANDLE, P])
    _bind(_K, "GetFileType", [W.HANDLE], W.DWORD)
    _bind(_K, "CreateDirectoryW", [W.LPCWSTR, P])
    _bind(_K, "ReadFile", [W.HANDLE, P, W.DWORD, P, P])
    _bind(_K, "WriteFile", [W.HANDLE, P, W.DWORD, P, P])
    _bind(_K, "FlushFileBuffers", [W.HANDLE])
    _bind(_K, "SetFileInformationByHandle", [W.HANDLE, C.c_int, P, W.DWORD])
    _bind(_K, "LockFileEx", [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, W.DWORD, P])
    _bind(_K, "UnlockFileEx", [W.HANDLE, W.DWORD, W.DWORD, W.DWORD, P])
    _bind(_K, "GetVolumeInformationW", [W.LPCWSTR, P, W.DWORD, P, P, P, P, W.DWORD])
    _bind(_A, "OpenProcessToken", [W.HANDLE, W.DWORD, P])
    _bind(_A, "GetTokenInformation", [W.HANDLE, C.c_int, P, W.DWORD, P])
    _bind(_A, "ConvertSidToStringSidW", [P, P])
    _bind(_A, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, P, P])
    _bind(_A, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, P, P, P, P, P], W.DWORD)
    _bind(_A, "GetAclInformation", [P, P, W.DWORD, C.c_int])
    _bind(_A, "GetAce", [P, W.DWORD, P])
    _bind(_A, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [P, W.DWORD, W.DWORD, P, P])
    _bind(_A, "GetSecurityDescriptorControl", [P, P, P])
    _bind(_A, "GetSecurityDescriptorDacl", [P, P, P, P])
    _bind(_A, "SetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, P, P, P, P], W.DWORD)


def _check(ok):
    if not ok:
        raise C.WinError(C.get_last_error())
    return ok


def _sid_text(sid):
    text = W.LPWSTR()
    _check(_A.ConvertSidToStringSidW(sid, C.byref(text)))
    try:
        return text.value
    finally:
        _K.LocalFree(C.cast(text, C.c_void_p))


def _user_sid():
    token = W.HANDLE()
    _check(_A.OpenProcessToken(_K.GetCurrentProcess(), 8, C.byref(token)))
    try:
        size = W.DWORD()
        _A.GetTokenInformation(token, 1, None, 0, C.byref(size))
        data = C.create_string_buffer(size.value)
        _check(_A.GetTokenInformation(token, 1, data, size, C.byref(size)))
        return _sid_text(C.cast(data, C.POINTER(C.c_void_p))[0])
    finally:
        _K.CloseHandle(token)


@contextlib.contextmanager
def _security(sddl=None):
    _api()
    if sddl is None:
        sddl = f"D:P(A;OICI;FA;;;{_user_sid()})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"
    descriptor = C.c_void_p()
    _check(_A.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
    try:
        yield _SA(C.sizeof(_SA), descriptor, False)
    finally:
        _K.LocalFree(descriptor)


def _absolute(path):
    _api()
    raw = os.fspath(path)
    if raw.startswith(("\\\\", "//")):
        raise _error()  # No UNC, device namespace or remote-share semantics.
    drive, tail = os.path.splitdrive(raw)
    if drive and (not re.fullmatch(r"[A-Za-z]:", drive) or not tail.startswith(("/", "\\"))):
        raise _error()
    # GetFullPathName (used by abspath) can remove trailing dots/spaces. Validate
    # the supplied spelling first, before Windows normalization loses evidence.
    for part in re.split(r"[/\\]", tail):
        if part in ("", ".", ".."):
            continue
        if (part.endswith((" ", ".")) or any(c in part for c in ':<>"|?*\x00')
                or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            raise _error()
    return Path(os.path.abspath(raw))


def _open(path, access=0x20080, disposition=3, security=None, share=3):
    handle = _K.CreateFileW(str(path), access, share, C.byref(security) if security else None,
                            disposition, 0x02200000, None)
    if handle == C.c_void_p(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        info = _Info()
        _check(_K.GetFileInformationByHandle(handle, C.byref(info)))
        if info.attributes & 0x400 or _K.GetFileType(handle) != 1:
            raise _error()
        return handle, info
    except BaseException:
        _K.CloseHandle(handle)
        raise


@contextlib.contextmanager
def directory(path, create=False, *, _handles=None):
    absolute = _absolute(path)
    handles = [] if _handles is None else _handles
    acquired = False
    try:
        # ACLs and local rename semantics are mandatory, not inferred from mode bits.
        fs = C.create_unicode_buffer(32)
        _check(_K.GetVolumeInformationW(absolute.anchor, None, 0, None, None, None, fs, len(fs)))
        if fs.value not in ("NTFS", "ReFS"):
            raise _error("UNSUPPORTED_FILESYSTEM")
        current = Path(absolute.anchor)
        for component in (None, *absolute.parts[1:]):
            if component is not None:
                current /= component
                if create:
                    with _security() as sa:
                        if not _K.CreateDirectoryW(str(current), C.byref(sa)) and C.get_last_error() != 183:
                            raise C.WinError(C.get_last_error())
            # A metadata-only handle does not enforce the same sharing checks.
            # FILE_LIST_DIRECTORY makes the handle a read-access participant.
            handle, info = _open(current, access=0x20081, share=1)
            handles.append(handle)
            if not info.attributes & 0x10:
                raise _error()
        acquired = True
        yield handles[-1]
    except OSError as exc:
        if acquired:
            raise  # Preserve caller exceptions, including missing files/lock contention.
        raise _error() from exc
    finally:
        for handle in reversed(handles):
            _K.CloseHandle(handle)


def validate_path(path):
    absolute = _absolute(path)
    with directory(absolute.parent):
        try:
            handle, _ = _open(absolute)
        except FileNotFoundError:
            return absolute
        else:
            _K.CloseHandle(handle)
    return absolute


def _relative(root, relative):
    from . import transcripciones_modelo
    parts = transcripciones_modelo._parts(relative)
    if any(":" in part for part in parts):
        raise _error()
    return _absolute(Path(root).joinpath(*parts))


def read_bytes(root, relative):
    path = _relative(root, relative)
    with directory(path.parent):
        try:
            handle, info = _open(path, 0x80000000, share=1)
        except OSError as exc:
            raise _error() from exc
        try:
            if info.attributes & 0x10:
                raise _error()
            chunks = []
            buffer = C.create_string_buffer(65536)
            count = W.DWORD()
            while True:
                _check(_K.ReadFile(handle, buffer, len(buffer), C.byref(count), None))
                if not count.value:
                    return b"".join(chunks)
                chunks.append(buffer.raw[:count.value])
        finally:
            _K.CloseHandle(handle)


def atomic_write(root, relative, data, *, immutable=True, preserve_acl=False):
    path = _relative(root, relative)
    pins = []
    with directory(path.parent, create=True, _handles=pins):
        temporary = path.parent / (".tmp-" + uuid.uuid4().hex)
        sddl = None
        if preserve_acl:
            try:
                sddl = security_descriptor(path)
            except FileNotFoundError:
                pass
        with _security(sddl) as sa:
            # Retain DELETE access ourselves, but do not share it. The temporary
            # entry cannot be removed by a competing writer before publication.
            handle, _ = _open(temporary, 0x40070000, 1, sa, share=1)
        published = False
        try:
            if sddl is not None and _handle_security_descriptor(handle) != sddl:
                # CreateFile can discard AUTO_INHERITED from its input SD.
                # Restore through the retained handle before publishing bytes;
                # never mask control bits in the preservation comparison.
                with _security(sddl) as sa:
                    control, revision = W.WORD(), W.DWORD()
                    _check(_A.GetSecurityDescriptorControl(sa.descriptor,
                        C.byref(control), C.byref(revision)))
                    _set_handle_dacl(handle, sa.descriptor, bool(control.value & 0x1000))
                if _handle_security_descriptor(handle) != sddl:
                    raise _error("PRESERVE_ACL_FAILED")
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + 1048576]
                count = W.DWORD()
                _check(_K.WriteFile(handle, chunk, len(chunk), C.byref(count), None))
                if not count.value:
                    raise OSError("Zero-length write")
                offset += count.value
            _check(_K.FlushFileBuffers(handle))
            validate_path(path)
            _allow_publication(path.parent, pins)
            try:
                _rename_file(handle, path, replace=not immutable)
                published = True
            except OSError as exc:
                error = getattr(exc, "winerror", None)
                if immutable and error in (80, 183):
                    if read_bytes(root, relative) != data:
                        raise _error("IMMUTABLE_CONFLICT")
                else:
                    raise
            _check(_K.FlushFileBuffers(handle))
        finally:
            try:
                if not published:
                    # Delete through our handle, never a path after releasing the
                    # last nonempty-directory guard. Close completes deletion.
                    delete = C.c_ubyte(1)
                    _check(_K.SetFileInformationByHandle(handle, 4, C.byref(delete), C.sizeof(delete)))
            finally:
                _K.CloseHandle(handle)


def _allow_publication(parent, pins):
    """Permit child rename while keeping each directory pinned against deletion.

    Call only after a non-delete-shared temporary file is open in final parent.
    Every directory is now nonempty through a pinned child or the pinned file;
    FSCTL_SET_REPARSE_POINT cannot turn a nonempty directory into a junction.
    Acquire the replacement pin before releasing the stricter one.
    """
    for index, candidate in enumerate([*reversed(parent.parents), parent]):
        replacement, _ = _open(candidate, access=0x20081, share=3)
        previous, pins[index] = pins[index], replacement
        _K.CloseHandle(previous)


def _rename_file(handle, path, *, replace):
    """Publish using our existing DELETE-capable handle, without reopening it."""
    name = str(path).encode("utf-16-le")
    size = max(C.sizeof(_RenameInfo), _RenameInfo.name.offset + len(name) + 2)
    buffer = C.create_string_buffer(size)
    info = _RenameInfo.from_buffer(buffer)
    info.replace, info.root, info.length = bool(replace), None, len(name)
    C.memmove(C.addressof(buffer) + _RenameInfo.name.offset, name, len(name))
    _check(_K.SetFileInformationByHandle(handle, 3, buffer, size))


@contextlib.contextmanager
def file_lock(path, blocking=True):
    path = _absolute(path)
    pins = []
    with directory(path.parent, create=True, _handles=pins), _security() as sa:
        handle, info = _open(path, 0xC0000000, 4, sa)
        overlapped = _Overlapped()
        acquired = False
        try:
            if info.attributes & 0x10:
                raise _error()
            # The persistent, non-delete-shared lock file keeps its parent
            # nonempty while callers publish files inside this lock context.
            _allow_publication(path.parent, pins)
            if not _K.LockFileEx(handle, 2 | (0 if blocking else 1), 0, 1, 0, C.byref(overlapped)):
                error = C.get_last_error()
                if error == 33:
                    raise BlockingIOError("Writer lock held")
                raise C.WinError(error)
            acquired = True
            yield
        finally:
            if acquired:
                _K.UnlockFileEx(handle, 0, 1, 0, C.byref(overlapped))
            _K.CloseHandle(handle)


def _private_handle(handle):
    dacl, descriptor, owner = C.c_void_p(), C.c_void_p(), C.c_void_p()
    result = _A.GetSecurityInfo(handle, 1, 5, C.byref(owner), None, C.byref(dacl), None, C.byref(descriptor))
    if result:
        raise C.WinError(result)
    try:
        if not dacl.value:
            return False
        control, revision = W.WORD(), W.DWORD()
        _check(_A.GetSecurityDescriptorControl(descriptor, C.byref(control), C.byref(revision)))
        if not control.value & 0x1000:  # SE_DACL_PROTECTED: parent ACL cannot widen it later.
            return False
        info = (W.DWORD * 3)()
        _check(_A.GetAclInformation(dacl, info, C.sizeof(info), 2))
        trusted = {_user_sid(), "S-1-5-18", "S-1-5-32-544"}
        if not owner.value or _sid_text(owner) not in trusted:
            return False
        for index in range(info[0]):
            ace = C.c_void_p()
            _check(_A.GetAce(dacl, index, C.byref(ace)))
            kind = C.c_ubyte.from_address(ace.value).value
            # Deny ACEs cannot grant access. Unknown/callback/object ACEs fail closed.
            if kind == 1:
                continue
            if kind != 0 or _sid_text(ace.value + 8) not in trusted:
                return False
        return True
    finally:
        _K.LocalFree(descriptor)


def is_private_directory(path):
    with directory(path) as handle:
        return _private_handle(handle)


def ensure_private_directory(path):
    with directory(path, create=True) as handle:
        if not _private_handle(handle):
            raise _error("PRIVATE_DIRECTORY_REQUIRED")
    return Path(path)


def security_descriptor(path):
    """Return the DACL as SDDL, for permission-preserving replacement and audit."""
    path = _absolute(path)
    with directory(path.parent):
        handle, _ = _open(path)
        try:
            return _handle_security_descriptor(handle)
        finally:
            _K.CloseHandle(handle)


def _handle_security_descriptor(handle):
    descriptor, text = C.c_void_p(), W.LPWSTR()
    try:
        result = _A.GetSecurityInfo(handle, 1, 4, None, None, None, None, C.byref(descriptor))
        if result:
            raise C.WinError(result)
        _check(_A.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, C.byref(text), None))
        return text.value
    finally:
        if text:
            _K.LocalFree(C.cast(text, C.c_void_p))
        if descriptor:
            _K.LocalFree(descriptor)


def _set_handle_dacl(handle, descriptor, protected):
    present, defaulted, dacl = W.BOOL(), W.BOOL(), C.c_void_p()
    _check(_A.GetSecurityDescriptorDacl(descriptor, C.byref(present),
        C.byref(dacl), C.byref(defaulted)))
    if not present:
        raise _error("PRIVATE_DIRECTORY_REQUIRED")
    result = _A.SetSecurityInfo(handle, 1,
        4 | (0x80000000 if protected else 0x20000000), None, None, dacl, None)
    if result:
        raise C.WinError(result)


def set_security_descriptor(path, sddl, *, protected=True):
    """Explicit ACL mutation for callers that already authorized permission changes."""
    path = _absolute(path)
    with directory(path.parent), _security(sddl) as sa:
        # SetSecurityInfo may read the current descriptor while changing
        # protection/inheritance; request READ_CONTROL in addition to WRITE_DAC.
        handle, _ = _open(path, 0x60080)
        try:
            # The object cannot be swapped while its non-delete-shared handle lives.
            _set_handle_dacl(handle, sa.descriptor, protected)
        finally:
            _K.CloseHandle(handle)


def flush_directory(path):
    """Validate confinement; Win32 exposes no unprivileged directory fsync.

    Callers rely on atomic_write's data flush and same-volume handle rename;
    this function deliberately does not claim a crash-durable directory barrier.
    """
    with directory(path):
        pass
