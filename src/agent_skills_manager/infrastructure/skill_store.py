from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path


class SkillStore:
    def children(self, root: Path) -> dict[str, Path]:
        if not root.is_dir():
            return {}
        return {
            entry.name: entry for entry in root.iterdir() if entry.is_dir() or entry.is_symlink()
        }

    def equivalent(self, left: Path, right: Path) -> bool:
        if not left.exists() or not right.exists():
            return False
        return self._digest(left) == self._digest(right)

    def replace(self, source: Path, destination: Path, link: bool) -> Path | None:
        source, destination = source.resolve(), destination.absolute()
        if not source.is_dir():
            raise ValueError(f"Skill source must be a directory: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup = (
            self._backup(destination) if destination.exists() or destination.is_symlink() else None
        )
        if link:
            destination.symlink_to(source, target_is_directory=True)
        else:
            shutil.copytree(source, destination, symlinks=True)
        return backup

    def _backup(self, path: Path) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        backup = path.with_name(f"{path.name}.agent-skills-manager-backup-{timestamp}")
        path.replace(backup)
        return backup

    def _digest(self, root: Path) -> str:
        digest = hashlib.sha256()
        for item in sorted(root.rglob("*"), key=lambda value: value.as_posix()):
            relative = item.relative_to(root).as_posix().encode()
            digest.update(relative)
            if item.is_symlink():
                digest.update(b"LINK" + str(item.readlink()).encode())
            elif item.is_file():
                digest.update(b"FILE" + item.read_bytes())
        return digest.hexdigest()
