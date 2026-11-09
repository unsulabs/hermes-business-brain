"""Platform-specific private-directory policy, without weakening POSIX guards."""
import os
import stat
from pathlib import Path


def is_link_or_reparse(path):
    path = Path(path)
    if path.is_symlink():
        return True
    if os.name == 'nt':
        try:
            return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except FileNotFoundError:
            pass
    return False


def private_directory(path, *, exist_ok=True):
    path = Path(path)
    if os.name == 'nt':
        from .windows_fs import ensure_private_directory
        if not exist_ok and path.exists():
            raise FileExistsError(path)
        ensure_private_directory(path)
    else:
        path.mkdir(mode=0o700, parents=True, exist_ok=exist_ok)
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError('The directory must be private to the owner')
