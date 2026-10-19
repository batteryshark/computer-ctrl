"""Static path validation and exclusive fresh-directory reservation (Python 3.11+).

Not a sandbox or protection against concurrent ancestor replacement. Use only
operator-controlled parents. No cleanup deletes existing or partially built data.
"""
import os
import stat
import sys


def validate_new_directory(raw: str) -> list[str]:
    # Inspect raw components BEFORE pathlib/normpath/mkdir can hide aliases.
    if not raw.startswith('/') or '\0' in raw:
        raise ValueError('destination must be an absolute path')
    parts = raw.split('/')[1:]
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('empty, dot and dot-dot path components are forbidden')
    missing = []
    path = ''
    for index, part in enumerate(parts):
        path += '/' + part
        try:
            mode = os.lstat(path).st_mode
        except FileNotFoundError:
            missing.append(path)
            continue
        if stat.S_ISLNK(mode):
            raise ValueError('symlink (including dangling link) in destination path')
        if index == len(parts) - 1:
            raise ValueError('destination already exists')
        if not stat.S_ISDIR(mode):
            raise ValueError('existing ancestor is not a directory')
    return missing


def reserve_destinations(app: str, build: str) -> None:
    # Both complete preflights precede ANY mkdir or build. With no raw aliases
    # or symlinks, these direct paths name the checked effective destinations.
    app_missing = validate_new_directory(app)
    build_missing = validate_new_directory(build)
    if app.startswith(build + '/') or build.startswith(app + '/') or app == build:
        raise ValueError('app and build destinations must be disjoint')
    # mkdir, not mkdir -p for final reservations: never accept an existing app
    # or build. Shared missing parents are created once. No overwrite/removal.
    created = set()
    for path in app_missing + build_missing:
        if path not in created:
            os.mkdir(path, 0o700)
            created.add(path)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError('expected app and build destinations')
        reserve_destinations(sys.argv[1], sys.argv[2])
    except (ValueError, OSError) as error:
        sys.exit(f'Refusing audio-helper destinations: {error}')
