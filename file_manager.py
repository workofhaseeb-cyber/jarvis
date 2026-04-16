"""
File Manager — Cross-platform file operations for JARVIS.
Handles voice commands like:
    - "Create a folder called Projects"
    - "Move this file to Desktop"
    - "Delete the file notes.txt"
    - "List files in Downloads"
    - "Rename report to final-report"
    - "Open the file budget.xlsx"

Works on Windows, macOS, and Linux.
"""

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger("jarvis.file_manager")

# Common path aliases
PATH_ALIASES = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
    "music": Path.home() / "Music",
    "videos": Path.home() / "Videos",
    "home": Path.home(),
}


def resolve_path(path_str: str) -> Path:
    """Resolve a path string, handling aliases and ~ expansion."""
    lower = path_str.lower().strip()
    if lower in PATH_ALIASES:
        return PATH_ALIASES[lower]
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = Path.home() / p
    return p


def create_folder(path: str, name: str = None) -> dict:
    """
    Create a folder.
    Examples:
        create_folder("Desktop", "MyProject")
        create_folder("Desktop/MyProject")
    """
    try:
        if name:
            full_path = resolve_path(path) / name
        else:
            full_path = resolve_path(path)

        full_path.mkdir(parents=True, exist_ok=True)
        log.info(f"Created folder: {full_path}")
        return {"success": True, "path": str(full_path), "message": f"Folder created at {full_path}"}
    except PermissionError:
        return {"success": False, "message": f"Permission denied creating folder at {path}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to create folder: {e}"}


def move_file(source: str, destination: str) -> dict:
    """
    Move a file or folder.
    Examples:
        move_file("Downloads/report.pdf", "Desktop")
        move_file("~/Downloads/report.pdf", "~/Documents/Reports")
    """
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)

        if not src.exists():
            return {"success": False, "message": f"Source not found: {src}"}

        if dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        log.info(f"Moved: {src} -> {dst}")
        return {"success": True, "message": f"Moved {src.name} to {dst.parent}"}
    except PermissionError:
        return {"success": False, "message": f"Permission denied moving {source}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to move file: {e}"}


def copy_file(source: str, destination: str) -> dict:
    """Copy a file or folder."""
    try:
        src = resolve_path(source)
        dst = resolve_path(destination)

        if not src.exists():
            return {"success": False, "message": f"Source not found: {src}"}

        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))

        log.info(f"Copied: {src} -> {dst}")
        return {"success": True, "message": f"Copied {src.name} to {dst}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to copy: {e}"}


def delete_file(path: str, confirm: bool = False) -> dict:
    """
    Delete a file or folder.
    Requires confirm=True as a safety measure.
    """
    if not confirm:
        return {
            "success": False,
            "message": "Deletion requires explicit confirmation. Pass confirm=True."
        }
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"success": False, "message": f"File not found: {p}"}

        if p.is_dir():
            shutil.rmtree(str(p))
        else:
            p.unlink()

        log.info(f"Deleted: {p}")
        return {"success": True, "message": f"Deleted {p.name}"}
    except PermissionError:
        return {"success": False, "message": f"Permission denied deleting {path}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to delete: {e}"}


def rename_file(path: str, new_name: str) -> dict:
    """Rename a file or folder."""
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"success": False, "message": f"File not found: {p}"}

        new_path = p.parent / new_name
        p.rename(new_path)
        log.info(f"Renamed: {p} -> {new_path}")
        return {"success": True, "message": f"Renamed to {new_name}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to rename: {e}"}


def list_files(path: str = "Desktop", show_hidden: bool = False) -> dict:
    """List files in a directory."""
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"success": False, "message": f"Directory not found: {p}", "files": []}

        items = []
        for item in sorted(p.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            items.append({
                "name": item.name,
                "type": "folder" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "path": str(item),
            })

        return {"success": True, "path": str(p), "files": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "message": f"Failed to list files: {e}", "files": []}


def open_file(path: str) -> dict:
    """Open a file with the default application (cross-platform)."""
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"success": False, "message": f"File not found: {p}"}

        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(p)], check=True)
        elif system == "Windows":
            os.startfile(str(p))
        else:
            subprocess.run(["xdg-open", str(p)], check=True)

        log.info(f"Opened: {p}")
        return {"success": True, "message": f"Opened {p.name}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to open file: {e}"}


def format_file_list_for_voice(files_result: dict) -> str:
    """Format file list result for JARVIS voice response."""
    if not files_result.get("success"):
        return files_result.get("message", "Could not list files.")

    files = files_result["files"]
    count = files_result["count"]
    path = files_result["path"]

    if count == 0:
        return f"The folder at {path} is empty, sir."

    folders = [f for f in files if f["type"] == "folder"]
    file_items = [f for f in files if f["type"] == "file"]

    result = f"{count} items in {Path(path).name}. "
    if folders:
        result += f"{len(folders)} folder{'s' if len(folders) != 1 else ''}: "
        result += ", ".join(f['name'] for f in folders[:3])
        if len(folders) > 3:
            result += f" and {len(folders) - 3} more"
        result += ". "
    if file_items:
        result += f"{len(file_items)} file{'s' if len(file_items) != 1 else ''}: "
        result += ", ".join(f['name'] for f in file_items[:3])
        if len(file_items) > 3:
            result += f" and {len(file_items) - 3} more"
        result += "."

    return result
