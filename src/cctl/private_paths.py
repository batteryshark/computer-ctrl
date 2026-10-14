"""Private helper-owned paths shared with the same user's limited Windows token."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess


def _windows_user_sid() -> str:
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                         wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        info = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 1, info, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(info, ctypes.POINTER(ctypes.c_void_p))[0]
        text = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.CloseHandle(token)


def create_private_directory(path: Path) -> None:
    """Create only a new helper directory; never change an existing path's ACL."""
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise ValueError("Artifact directory must be a real directory")
        return
    path.mkdir(parents=True, mode=0o700)
    if os.name == "nt":
        # Python 3.13 mode0700 can grant OWNER RIGHTS to the elevated token's
        # Administrators owner, excluding this user's Limited child token.
        # Add the actual user SID, never Everyone/Users, on this new directory.
        sid = _windows_user_sid()
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                                 f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise OSError("Could not grant the same Windows user access to its private artifact directory")
