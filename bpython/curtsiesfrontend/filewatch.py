import time
import os
from collections import defaultdict

from bpython import importcompletion

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    def ModuleChangedEventHandler(*args):
        return None
else:
    class ModuleChangedEventHandler(FileSystemEventHandler):
        def __init__(self, paths, on_change):
            self.dirs = defaultdict(set)
            self.on_change = on_change
            self.modules_to_add_later = []
            self.observer = Observer()
            self.old_dirs = defaultdict(set)
            self.started = False
            for path in paths:
                self.add_module(path)

        def reset(self):
            self.dirs = defaultdict(set)
            del self.modules_to_add_later[:]
            self.old_dirs = defaultdict(set)
            self.observer.unschedule_all()

        def add_module(self, path):
            """Add a python module to track changes to"""
            path = os.path.abspath(path)
            for suff in importcompletion.SUFFIXES:
                if path.endswith(suff):
                    path = path[:-len(suff)]
                    break
            dirname = os.path.dirname(path)
            if dirname not in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
                self.dirs[os.path.dirname(path)].add(path)

        def add_module_later(self, path):
            self.modules_to_add_later.append(path)

        def activate(self):
            if not self.started:
                self.started = True
                self.observer.start()
            self.dirs = self.old_dirs
            for dirname in self.dirs:
                self.observer.schedule(self, dirname, recursive=False)
            for module in self.modules_to_add_later:
                self.add_module(module)
            del self.modules_to_add_later[:]

        def deactivate(self):
            self.observer.unschedule_all()
            self.old_dirs = self.dirs
            self.dirs = defaultdict(set)

        def on_any_event(self, event):
            dirpath = os.path.dirname(event.src_path)
            paths = [path + '.py' for path in self.dirs[dirpath]]
            if event.src_path in paths:
                self.on_change(files_modified=[event.src_path])

if __name__ == '__main__':
    m = ModuleChangedEventHandler([])
    m.add_module('./wdtest.py')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        m.observer.stop()
    m.observer.join()

