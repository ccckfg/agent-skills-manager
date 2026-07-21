from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path


BACKUP_MARKER = ".agent-skills-manager-backup-"
IGNORED_COPY_PATTERNS = ("__pycache__", "*.pyc", ".DS_Store")


class SkillStore:
    def children(self, root: Path) -> dict[str, Path]:
        if not root.is_dir():
            return {}
        return {entry.name: entry for entry in root.iterdir() if self._is_visible_skill(entry)}

    def equivalent(self, left: Path, right: Path) -> bool:
        if not left.exists() or not right.exists():
            return False
        return self.digest(left) == self.digest(right)

    def is_link(self, path: Path) -> bool:
        """Recognize POSIX links and Windows directory junctions."""
        if path.is_symlink():
            return True
        junction_check = getattr(path, "is_junction", None)
        if callable(junction_check) and junction_check():
            return True
        try:
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
        except OSError:
            return False
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

    def points_to(self, path: Path, source: Path) -> bool:
        """Return whether a link or junction resolves to the canonical Skill."""
        if not self.is_link(path) or not path.exists():
            return False
        return path.resolve() == source.resolve()

    def replace(
        self,
        source: Path,
        destination: Path,
        link: bool,
        backup_root: Path | None = None,
    ) -> Path | None:
        source, destination = source.resolve(), destination.absolute()
        if not source.is_dir():
            raise ValueError(f"Skill source must be a directory: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = (
            self.backup(destination, backup_root)
            if destination.exists() or self.is_link(destination)
            else None
        )
        try:
            if link:
                self._create_link(source, destination)
            else:
                shutil.copytree(
                    source,
                    destination,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(*IGNORED_COPY_PATTERNS),
                )
        except Exception:
            if backup and not destination.exists() and not self.is_link(destination):
                backup.replace(destination)
            raise
        return backup

    def backup(self, path: Path, backup_root: Path | None = None) -> Path:
        """Move a Skill to a timestamped, recoverable backup."""
        if not path.exists() and not self.is_link(path):
            raise FileNotFoundError(path)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        if backup_root:
            backup_root.mkdir(parents=True, exist_ok=True)
            destination = backup_root / f"{path.name}-{timestamp}"
        else:
            destination = path.with_name(f"{path.name}{BACKUP_MARKER}{timestamp}")
        path.replace(destination)
        return destination

    def digest(self, root: Path) -> str:
        """Build a stable content digest while ignoring generated clutter."""
        digest = hashlib.sha256()
        for item in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
            if "__pycache__" in item.parts or item.suffix == ".pyc" or item.name == ".DS_Store":
                continue
            relative = item.relative_to(root).as_posix().encode()
            digest.update(relative)
            if item.is_symlink():
                digest.update(b"LINK" + str(item.readlink()).encode())
            elif item.is_file():
                digest.update(b"FILE" + item.read_bytes())
        return digest.hexdigest()

    def _is_visible_skill(self, entry: Path) -> bool:
        if entry.name.startswith(".") or BACKUP_MARKER in entry.name:
            return False
        return self.is_link(entry) or (entry.is_dir() and (entry / "SKILL.md").is_file())

    def _create_link(self, source: Path, destination: Path) -> None:
        if os.name != "nt":
            destination.symlink_to(source, target_is_directory=True)
            return
        command = os.environ.get("COMSPEC", "cmd.exe")
        result = subprocess.run(
            [command, "/c", "mklink", "/J", str(destination), str(source)],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip()
            raise OSError(f"Could not create directory junction: {message}")
