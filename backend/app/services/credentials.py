from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from app.config import get_settings
from app.paths import get_credentials_dir


class CredentialStorageUnavailable(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialStorageUnavailable("Windows DPAPI is unavailable on this platform")
    source, keepalive = _blob(value)
    output = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "Notice Hub", None, None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del keepalive


def _unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialStorageUnavailable("Windows DPAPI is unavailable on this platform")
    source, keepalive = _blob(value)
    output = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)
        del keepalive


class CredentialStore:
    def __init__(self, directory: Path | None = None) -> None:
        settings = get_settings()
        self.directory = directory or get_credentials_dir(settings.environment, settings.app_data_dir)
        self._volatile: dict[str, str] = {}

    def _path(self, reference: str) -> Path:
        safe = "".join(character for character in reference if character.isalnum() or character in {"-", "_"})
        if safe != reference or not safe:
            raise ValueError("invalid credential reference")
        return self.directory / f"{safe}.dpapi"

    def save(self, reference: str, secret: str) -> None:
        if get_settings().environment == "test" and os.name != "nt":
            self._volatile[reference] = secret
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(reference)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(_protect(secret.encode("utf-8")))
        temporary.replace(path)

    def load(self, reference: str) -> str | None:
        if reference in self._volatile:
            return self._volatile[reference]
        path = self._path(reference)
        if not path.exists():
            return None
        return _unprotect(path.read_bytes()).decode("utf-8")

    def delete(self, reference: str) -> None:
        self._volatile.pop(reference, None)
        self._path(reference).unlink(missing_ok=True)


credential_store = CredentialStore()
