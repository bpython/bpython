import time
import os
from collections import defaultdict

from bpython import importcompletion

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ModuleChangedEventHandler(FileSystemEventHandler):
    def __init__(self, paths, on_change):
        self.dirs = defaultdict(set)
        self.on_change = on_change
        self.observer = Observer()
        for path in paths:
            self.add_module(path)
        self.observer.start()

    def reset(self):
        self.dirs = defaultdict(set)
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

    def on_any_event(self, event):
        dirpath = os.path.dirname(event.src_path)
        paths = [path + '.py' for path in self.dirs[dirpath]]
        if event.src_path in paths:
            self.on_change(event.src_path)

if __name__ == '__main__':
    m = ModuleChangedEventHandler([])
    m.add_module('./wdtest.py')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        m.observer.stop()
    m.observer.join()
