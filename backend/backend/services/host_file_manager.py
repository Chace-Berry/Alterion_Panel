"""
Host (outside-Docker) file manager helper.

Provides safe path resolution under a configured host root and common
file operations. Designed to be used by FileManagerViewSet when `pk`
starts with `host-`.
"""
import os
import stat
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime

DEFAULT_WINDOWS_ROOT = None  # Will use Documents folder
DEFAULT_LINUX_ROOT = "/var/www/data"


def get_host_root() -> Path:
    """Return the configured host root path.

    Env var `ALTERION_HOST_ROOT` overrides defaults.
    For Windows: defaults to user's Documents folder
    For Linux/Unix: defaults to /var/www/data
    """
    env = os.environ.get("ALTERION_HOST_ROOT")
    if env:
        return Path(env)
    if os.name == "nt":
        # Use Documents folder on Windows
        return Path.home() / "Documents"
    return Path(DEFAULT_LINUX_ROOT)


def resolve_host_path(requested: str) -> Path:
    """Resolve and sanitize a requested path under the host root.

    - Expands env and user (~)
    - Normalizes and resolves to absolute path
    - Ensures the resulting path is inside host root (prevents traversal)
    
    If no path is requested or it's empty, returns the host root.
    """
    root = get_host_root().resolve()
    
    # If no path requested, return root
    if not requested or requested.strip() == "":
        return root
    
    # Expand and normalize
    expanded = os.path.expandvars(os.path.expanduser(requested))
    # If the requested path is relative, join to root
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = root / candidate
    # Resolve symlinks and relative segments
    try:
        resolved = candidate.resolve(strict=False)
    except Exception:
        # If resolution fails (non-existent), still build a path
        resolved = candidate
    # Enforce containment
    try:
        resolved.relative_to(root)
    except Exception:
        raise PermissionError(f"Path escapes host root: {resolved}")
    return resolved


def list_dir(path: Path):
    """List directory contents and basic metadata."""
    if not path.exists():
        raise FileNotFoundError(str(path))
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    items = []
    for entry in path.iterdir():
        try:
            st = entry.stat()
            is_dir = stat.S_ISDIR(st.st_mode)
            items.append({
                "name": entry.name,
                "path": str(entry),
                "size": 0 if is_dir else st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
                "permissions": oct(stat.S_IMODE(st.st_mode)),
                "type": "directory" if is_dir else "file",
                "is_directory": is_dir,
                "is_file": stat.S_ISREG(st.st_mode),
                "is_link": stat.S_ISLNK(st.st_mode),
            })
        except Exception as e:
            items.append({"name": entry.name, "path": str(entry), "error": str(e)})
    items.sort(key=lambda x: (not x.get("is_directory", False), x["name"].lower()))
    return items


def read_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path: Path, content: str):
    # Ensure parent exists
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def create_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def delete_path(path: Path):
    if path.is_dir():
        # Only delete empty directories to be safe
        try:
            path.rmdir()
        except OSError as e:
            # Fallback: remove tree if explicitly allowed (not enabling by default)
            raise e
    else:
        path.unlink(missing_ok=True)


def rename_path(old_path: Path, new_path: Path):
    # Ensure both are under root
    root = get_host_root().resolve()
    for p in (old_path, new_path):
        rp = p.resolve(strict=False)
        try:
            rp.relative_to(root)
        except Exception:
            raise PermissionError(f"Path escapes host root: {rp}")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
