import os
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from typing import Protocol

from .. import importcompletion


class ModuleWatcher(Protocol):
    dirs: dict[str, set[str]]
    activated: bool

    def track_module(self, path: str) -> None: ...
    def reset(self) -> None: ...
    def activate(self) -> None: ...
    def deactivate(self) -> None: ...


try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:

    def ModuleChangedEventHandler(
        paths: Iterable[str], on_change: Callable[[Sequence[str]], None]
    ) -> ModuleWatcher | None:
        return None

else:

    class ModuleChangedEventHandler(FileSystemEventHandler):  # type: ignore [no-redef]
        def __init__(
            self,
            paths: Iterable[str],
            on_change: Callable[[Sequence[str]], None],
        ) -> None:
            self.dirs: dict[str, set[str]] = defaultdict(set)
            self.on_change = on_change
            self.modules_to_add_later: list[str] = []
            self.observer = Observer()
            self.started = False
            self.activated = False
            for path in paths:
                self._add_module(path)

            super().__init__()

        def reset(self) -> None:
            self.dirs.clear()
            self.modules_to_add_later.clear()
            self.observer.unschedule_all()

        def _add_module(self, path: str) -> None:
            """Add a python module to track changes"""
            path = os.path.abspath(path)
            for suff in importcompletion.SUFFIXES:
                if path.endswith(suff):
                    path = path[: -len(suff)]
                    break
            dirname = os.path.dirname(path)
            if dirname not in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
            self.dirs[dirname].add(path)

        def _add_module_later(self, path: str) -> None:
            self.modules_to_add_later.append(path)

        def track_module(self, path: str) -> None:
            """
            Begins tracking this if activated, or remembers to track later.
            """
            if self.activated:
                self._add_module(path)
            else:
                self._add_module_later(path)

        def activate(self) -> None:
            if self.activated:
                raise ValueError(f"{self!r} is already activated.")
            if not self.started:
                self.started = True
                self.observer.start()
            for dirname in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
            for module in self.modules_to_add_later:
                self._add_module(module)
            self.modules_to_add_later.clear()
            self.activated = True

        def deactivate(self) -> None:
            if not self.activated:
                raise ValueError(f"{self!r} is not activated.")
            self.observer.unschedule_all()
            self.activated = False

        def on_any_event(self, event: FileSystemEvent) -> None:
            src_path = os.fsdecode(event.src_path)
            dirpath = os.path.dirname(src_path)
            if any(src_path == f"{path}.py" for path in self.dirs[dirpath]):
                self.on_change((src_path,))
