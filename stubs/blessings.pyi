from typing import ContextManager, Text, IO

class Terminal:
    def __init__(self, stream=None, force_styling=False):
        # type: (IO, bool) -> None
        pass
    def location(self, x=None, y=None):
        # type: (int, int) -> ContextManager
        pass
    @property
    def hide_cursor(self):
        # type: () -> Text
        pass
    @property
    def normal_cursor(self):
        # type: () -> Text
        pass
    @property
    def height(self):
        # type: () -> int
        pass
    @property
    def width(self):
        # type: () -> int
        pass
    def fullscreen(self):
        # type: () -> ContextManager
        pass
    def move(self, y, x):
        # type: (int, int) -> Text
        pass
    @property
    def clear_eol(self):
        # type: () -> Text
        pass
    @property
    def clear_bol(self):
        # type: () -> Text
        pass
    @property
    def clear_eos(self):
        # type: () -> Text
        pass
    @property
    def clear_eos(self):
        # type: () -> Text
        pass
