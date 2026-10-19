"""Pure mocked filesystem checks; never compile, sign or install the helper."""
import importlib.util
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load_guard():
    path = Path(__file__).parents[1] / "packaging/macos/audio_destination_guard.py"
    spec = importlib.util.spec_from_file_location("audio_destination_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise_guard():
    """Return the number of assertions groups, using only a fake filesystem."""
    guard = load_guard()
    entries = {"/": stat.S_IFDIR, "/owned": stat.S_IFDIR}
    created = []

    def lstat(path):
        if path not in entries:
            raise FileNotFoundError(path)
        return SimpleNamespace(st_mode=entries[path])

    def mkdir(path, mode):
        assert path not in entries
        assert mode == 0o700
        entries[path] = stat.S_IFDIR
        created.append(path)

    def refuses(call):
        before = list(created)
        try:
            call()
        except (ValueError, OSError):
            assert created == before, "preflight refusal must not write"
        else:
            raise AssertionError("expected refusal")

    with patch.object(guard, "os", SimpleNamespace(lstat=lstat, mkdir=mkdir)):
        for raw in ("relative", "/owned//app", "/owned/./app", "/owned/../app", "/owned/app/", "/owned/a\0b"):
            refuses(lambda raw=raw: guard.validate_new_directory(raw))
        entries["/owned/link"] = stat.S_IFLNK
        refuses(lambda: guard.validate_new_directory("/owned/link/app"))
        entries["/owned/file"] = stat.S_IFREG
        refuses(lambda: guard.validate_new_directory("/owned/file/app"))
        refuses(lambda: guard.validate_new_directory("/owned"))
        refuses(lambda: guard.reserve_destinations("/owned/new", "/owned/file/build"))
        refuses(lambda: guard.reserve_destinations("/owned/new", "/owned/new/build"))
        refuses(lambda: guard.reserve_destinations("/owned/new/build", "/owned/new"))
        refuses(lambda: guard.reserve_destinations("/owned/new", "/owned/new"))
        guard.reserve_destinations("/owned/shared/App Name.app", "/owned/shared/build")
        assert created == ["/owned/shared", "/owned/shared/App Name.app", "/owned/shared/build"]
        refuses(lambda: guard.reserve_destinations("/owned/shared/App Name.app", "/owned/other"))
    return 15


def test_audio_destination_guard():
    assert exercise_guard() == 15
