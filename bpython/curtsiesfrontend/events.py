"""Non-keyboard events used in bpython curtsies REPL"""
import time

import curtsies.events


class ReloadEvent(curtsies.events.Event):
    """Request to rerun REPL session ASAP because imported modules changed"""

    def __init__(self, files_modified=("?",)):
        self.files_modified = files_modified

    def __repr__(self):
        return "<ReloadEvent from %s>" % (" & ".join(self.files_modified))


class RefreshRequestEvent(curtsies.events.Event):
    """Request to refresh REPL display ASAP"""

    def __repr__(self):
        return "<RefreshRequestEvent for now>"


class ScheduledRefreshRequestEvent(curtsies.events.ScheduledEvent):
    """Request to refresh the REPL display at some point in the future

    Used to schedule the disappearance of status bar message that only shows
    for a few seconds"""

    def __init__(self, when):
        super().__init__(when)

    def __repr__(self):
        return "<RefreshRequestEvent for %s seconds from now>" % (
            self.when - time.time()
        )


class RunStartupFileEvent(curtsies.events.Event):
    """Request to run the startup file."""


class UndoEvent(curtsies.events.Event):
    """Request to undo."""

    def __init__(self, n=1):
        self.n = n
