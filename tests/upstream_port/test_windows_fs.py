"""Ported upstream test_windows_fs.py: native Windows filesystem security

backend. The class keeps its explicit platform gate (upstream design): on
POSIX every method skips with the upstream reason, so the module still must be
importable, which this file verifies on every platform.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine import windows_fs as fs


@unittest.skipUnless(os.name == "nt", "native Windows filesystem backend")
class WindowsFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "private"
        fs.ensure_private_directory(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_private_acl_is_real_and_existing_broad_acl_is_rejected(self):
        self.assertTrue(fs.is_private_directory(self.root))
        original = fs.security_descriptor(self.root)
        try:
            fs.set_security_descriptor(self.root, "D:P(A;OICI;FA;;;WD)")
            self.assertFalse(fs.is_private_directory(self.root))
            with self.assertRaisesRegex(ValueError, "PRIVATE_DIRECTORY_REQUIRED"):
                fs.ensure_private_directory(self.root)
            self.assertFalse(fs.is_private_directory(self.root))
        finally:
            fs.set_security_descriptor(self.root, original)

    def test_write_read_immutable_conflict_and_mutable_replace(self):
        fs.atomic_write(self.root, "nested/payload.bin", b"original\x00")
        self.assertEqual(fs.read_bytes(self.root, "nested/payload.bin"), b"original\x00")
        fs.atomic_write(self.root, "nested/payload.bin", b"original\x00")
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_CONFLICT"):
            fs.atomic_write(self.root, "nested/payload.bin", b"different")
        fs.atomic_write(self.root, "nested/payload.bin", b"updated", immutable=False)
        self.assertEqual(fs.read_bytes(self.root, "nested/payload.bin"), b"updated")
        self.assertFalse(list(self.root.rglob(".tmp-*")))

    def test_permission_preserving_replace(self):
        target = self.root / "note.md"
        fs.atomic_write(self.root, target.name, b"old")
        original_creation_acl = fs.security_descriptor(target)
        fs.atomic_write(self.root, target.name, b"no-ai", immutable=False, preserve_acl=True)
        self.assertEqual(fs.security_descriptor(target), original_creation_acl)
        fs.set_security_descriptor(target,
                                   f"D:P(A;;FA;;;{fs._user_sid()})(A;;FR;;;WD)")
        before = fs.security_descriptor(target)
        fs.atomic_write(self.root, target.name, b"new", immutable=False, preserve_acl=True)
        self.assertEqual(fs.security_descriptor(target), before)
        fs.set_security_descriptor(target,
                                   f"D:(A;;FA;;;{fs._user_sid()})(A;;FR;;;WD)", protected=False)
        unprotected_acl = fs.security_descriptor(target)
        fs.atomic_write(self.root, target.name, b"unprotected", immutable=False,
                        preserve_acl=True)
        self.assertEqual(fs.security_descriptor(target), unprotected_acl)

    def test_preserve_acl_creates_new_destination(self):
        fs.atomic_write(self.root, "new/journal.json", b"new", immutable=False,
                        preserve_acl=True)
        self.assertEqual(fs.read_bytes(self.root, "new/journal.json"), b"new")

    def test_publication_inside_writer_lock_keeps_parent_pinned(self):
        with fs.file_lock(self.root / ".writer.lock"):
            with self.assertRaises(OSError):
                self.root.rename(self.root.with_name("moved-root"))
            fs.atomic_write(self.root, "payload", b"within lock")
            self.assertEqual(fs.read_bytes(self.root, "payload"), b"within lock")

    def test_publication_handover_rejects_in_place_junction_mutation(self):
        import struct
        from unittest import mock
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        native_rename = fs._rename_file
        ioctl = fs._K.DeviceIoControl
        ioctl.argtypes = [fs.W.HANDLE, fs.W.DWORD, fs.C.c_void_p, fs.W.DWORD,
                          fs.C.c_void_p, fs.W.DWORD, fs.C.c_void_p, fs.C.c_void_p]
        ioctl.restype = fs.W.BOOL
        substitute = ("\\??\\" + str(outside)).encode("utf-16-le")
        printable = str(outside).encode("utf-16-le")
        paths = substitute + b"\0\0" + printable + b"\0\0"
        payload = struct.pack("<IHHHHHH", 0xA0000003, 8 + len(paths), 0,
                              0, len(substitute), len(substitute) + 2, len(printable)) + paths

        def check_handover(handle, path, *, replace):
            temporary, = path.parent.glob(".tmp-*")
            with self.assertRaises(OSError):
                temporary.write_bytes(b"tampered")
            with self.assertRaises(OSError):
                temporary.unlink()
            for candidate in (path.parent, self.root):
                directory_handle, _ = fs._open(candidate, 0x40000000, share=3)
                try:
                    returned = fs.W.DWORD()
                    success = ioctl(directory_handle, 0x900A4, payload, len(payload),
                                    None, 0, fs.C.byref(returned), None)
                    error = fs.C.get_last_error()
                    if success:
                        deletion = struct.pack("<IHH", 0xA0000003, 0, 0)
                        ioctl(directory_handle, 0x900AC, deletion, len(deletion),
                              None, 0, fs.C.byref(returned), None)
                    self.assertFalse(success)
                    self.assertEqual(error, 145)  # ERROR_DIR_NOT_EMPTY
                finally:
                    fs._K.CloseHandle(directory_handle)
            native_rename(handle, path, replace=replace)

        with mock.patch.object(fs, "_rename_file", side_effect=check_handover):
            fs.atomic_write(self.root, "nested/payload", b"confined")
        self.assertEqual(fs.read_bytes(self.root, "nested/payload"), b"confined")
        self.assertEqual(list(outside.iterdir()), [])

    def test_directory_preserves_body_exception_types(self):
        for exception in (FileNotFoundError("missing"), BlockingIOError("busy"),
                          OSError("body")):
            with self.subTest(exception=type(exception)), \
                 self.assertRaises(type(exception)) as raised:
                with fs.directory(self.root):
                    raise exception
            self.assertIs(raised.exception, exception)

    def test_restrictive_but_unprotected_acl_is_rejected(self):
        child = self.root / "child"
        fs.ensure_private_directory(child)
        fs.set_security_descriptor(child, f"D:(A;OICI;FA;;;{fs._user_sid()})",
                                   protected=False)
        self.assertFalse(fs.is_private_directory(child))
        with self.assertRaisesRegex(ValueError, "PRIVATE_DIRECTORY_REQUIRED"):
            fs.ensure_private_directory(child)

    def test_windows_aliases_and_streams_rejected(self):
        for relative in ("file:secret", "NUL", "name.", "name ", "C:escape", "../escape"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                fs.atomic_write(self.root, relative, b"bad")

    def test_pinned_directory_cannot_be_renamed(self):
        nested = self.root / "nested"
        fs.ensure_private_directory(nested)
        with fs.directory(nested):
            with self.assertRaises(OSError):
                nested.rename(self.root / "moved")
            with self.assertRaises(OSError):
                self.root.rename(self.root.with_name("moved-root"))

    def test_junction_ancestor_rejected(self):
        import subprocess
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "secret").write_bytes(b"outside")
        junction = self.root / "junction"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                       check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(ValueError, "UNSAFE_PATH"):
                fs.read_bytes(self.root, "junction/secret")
            with self.assertRaisesRegex(ValueError, "UNSAFE_PATH"):
                fs.atomic_write(self.root, "junction/created", b"bad")
            self.assertFalse((outside / "created").exists())
        finally:
            junction.rmdir()

    def test_native_lock_blocks_and_releases_on_process_death(self):
        import subprocess
        lock = self.root / ".writer.lock"
        code = ("import sys,time;sys.path.insert(0,sys.argv[1]);import windows_fs as f;"
                "ctx=f.file_lock(sys.argv[2]);ctx.__enter__();print('LOCKED',flush=True);"
                "time.sleep(60)")
        process = subprocess.Popen([sys.executable, "-c", code,
                                    str(Path(fs.__file__).parent), str(lock)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "LOCKED")
            with self.assertRaises(BlockingIOError):
                with fs.file_lock(lock, blocking=False):
                    pass
            process.kill()
            process.wait(timeout=10)
            with fs.file_lock(lock, blocking=False):
                pass
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
