import hashlib
import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    junction_check = getattr(path, "is_junction", None)
    if callable(junction_check) and junction_check():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return False


def child_directories(root: Path) -> Dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        entry.name: entry
        for entry in root.iterdir()
        if not entry.name.startswith(".")
        and (entry.is_symlink() or (entry.is_dir() and (entry / "SKILL.md").is_file()))
    }


def digest(root: Path) -> str:
    checksum = hashlib.sha256()
    for item in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
        if "__pycache__" in item.parts or item.suffix == ".pyc" or item.name == ".DS_Store":
            continue
        checksum.update(item.relative_to(root).as_posix().encode("utf-8"))
        if item.is_symlink():
            checksum.update(b"LINK" + str(item.readlink()).encode("utf-8"))
        elif item.is_file():
            checksum.update(b"FILE" + item.read_bytes())
    return checksum.hexdigest()


def equivalent(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and digest(left) == digest(right)


def create_link(source: Path, destination: Path) -> None:
    if os.name != "nt":
        destination.symlink_to(source, target_is_directory=True)
        return
    command = os.environ.get("COMSPEC", "cmd.exe")
    result = subprocess.run(
        [command, "/c", "mklink", "/J", str(destination), str(source)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise OSError("Could not create directory junction: {}".format(message))


def backup(path: Path, backup_root: Optional[Path] = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    if backup_root:
        backup_root.mkdir(parents=True, exist_ok=True)
        destination = backup_root / "{}-{}".format(path.name, stamp)
    else:
        destination = path.with_name("{}.agent-skills-manager-backup-{}".format(path.name, stamp))
    path.replace(destination)
    return destination


def replace(
    source: Path,
    destination: Path,
    mode: str,
    backup_root: Optional[Path] = None,
) -> Optional[Path]:
    source = source.resolve()
    destination = destination.absolute()
    if not source.is_dir():
        raise ValueError("Skill source must be a directory: {}".format(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    old = None
    if destination.exists() or destination.is_symlink():
        old = backup(destination, backup_root)
    if mode == "link":
        create_link(source, destination)
    else:
        shutil.copytree(
            source,
            destination,
            symlinks=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
    return old
