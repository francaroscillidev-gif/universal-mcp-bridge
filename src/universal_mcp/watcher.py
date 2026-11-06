import asyncio
import os
import logging
from pathlib import Path
from typing import Callable, Optional, Set

logger = logging.getLogger("universal_mcp.watcher")

class FileWatcher:
    """
    Poll-based file watcher that checks modification timestamps of registered
    scripts, specs, and directories without requiring heavy platform-dependent C-extensions.
    """
    def __init__(self, check_interval_seconds: float = 2.0):
        self.interval = check_interval_seconds
        self.watched_paths: Set[str] = set()
        self.snapshots: dict[str, float] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def watch_path(self, path: str):
        abs_p = os.path.abspath(path)
        self.watched_paths.add(abs_p)
        self._record_snapshot(abs_p)

    def _record_snapshot(self, path: str):
        p = Path(path)
        if not p.exists():
            return
        if p.is_file():
            self.snapshots[str(p)] = p.stat().st_mtime
        elif p.is_dir():
            for item in p.rglob("*"):
                if item.is_file() and not item.name.startswith("."):
                    self.snapshots[str(item)] = item.stat().st_mtime

    def check_for_changes(self) -> bool:
        changed = False
        current_files = set()

        for base_path in list(self.watched_paths):
            p = Path(base_path)
            if not p.exists():
                continue
            if p.is_file():
                current_files.add(str(p))
                mtime = p.stat().st_mtime
                if str(p) not in self.snapshots or self.snapshots[str(p)] != mtime:
                    self.snapshots[str(p)] = mtime
                    changed = True
            elif p.is_dir():
                for item in p.rglob("*"):
                    if item.is_file() and not item.name.startswith("."):
                        current_files.add(str(item))
                        mtime = item.stat().st_mtime
                        if str(item) not in self.snapshots or self.snapshots[str(item)] != mtime:
                            self.snapshots[str(item)] = mtime
                            changed = True

        # Check for deleted files
        for old_file in list(self.snapshots.keys()):
            if old_file not in current_files and not Path(old_file).exists():
                del self.snapshots[old_file]
                changed = True

        return changed

    async def start(self, on_change: Callable[[], None]):
        self._running = True
        while self._running:
            await asyncio.sleep(self.interval)
            try:
                if self.check_for_changes():
                    on_change()
            except Exception as e:
                logger.error(f"Error in FileWatcher: {e}")

    def stop(self):
        self._running = False
