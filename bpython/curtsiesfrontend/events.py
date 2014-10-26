"""Non-keybaord events used in bpython curtsies REPL"""
import time

import curtsies.events


class ReloadEvent(curtsies.events.Event):
    """Request to rerun REPL session ASAP because imported modules changed"""
    def __init__(self, files_modified=('?',)):
        self.files_modified = files_modified

    def __repr__(self):
        return "<ReloadEvent from %s>" % (' & '.join(self.files_modified))


class RefreshRequestEvent(curtsies.events.Event):
    """Request to refresh REPL display ASAP"""
    def __init__(self, who='?'):
        self.who = who

    def __repr__(self):
        return "<RefreshRequestEvent from %r for now>" % (self.who,)


class ScheduledRefreshRequestEvent(curtsies.events.ScheduledEvent):
    """Request to refresh the REPL display at some point in the future

    Used to schedule the dissapearance of status bar message that only show
    for a few seconds"""
    def __init__(self, when, who='?'):
        self.who = who
        self.when = when  # time.time() + how long

    def __repr__(self):
        return ("<RefreshRequestEvent from %r for %s seconds from now>" %
                (self.who, self.when - time.time()))
