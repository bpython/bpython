#!/usr/bin/env python
#
# The MIT License
#
# Copyright (c) 2010 Marien Zwart
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


"""bpython backend based on Urwid.

Based on Urwid 0.9.9.

This steals many things from bpython's "cli" backend.

This is still *VERY* rough.
"""


from __future__ import absolute_import, with_statement, division

import sys
import os
import locale
from types import ModuleType
from optparse import Option

from pygments.token import Token

from bpython import args as bpargs, repl
from bpython.formatter import theme_map
from bpython.importcompletion import find_coroutine

import urwid

py3 = sys.version_info[0] == 3

Parenthesis = Token.Punctuation.Parenthesis

# Urwid colors are:
# 'black', 'dark red', 'dark green', 'brown', 'dark blue',
# 'dark magenta', 'dark cyan', 'light gray', 'dark gray',
# 'light red', 'light green', 'yellow', 'light blue',
# 'light magenta', 'light cyan', 'white'
# and bpython has:
# blacK, Red, Green, Yellow, Blue, Magenta, Cyan, White, Default

COLORMAP = {
    'k': 'black',
    'r': 'dark red', # or light red?
    'g': 'dark green', # or light green?
    'y': 'yellow',
    'b': 'dark blue', # or light blue?
    'm': 'dark magenta', # or light magenta?
    'c': 'dark cyan', # or light cyan?
    'w': 'white',
    'd': 'default',
    }


class Statusbar(object):

    """Statusbar object, ripped off from bpython.cli.

    This class provides the status bar at the bottom of the screen.
    It has message() and prompt() methods for user interactivity, as
    well as settext() and clear() methods for changing its appearance.

    The check() method needs to be called repeatedly if the statusbar is
    going to be aware of when it should update its display after a message()
    has been called (it'll display for a couple of seconds and then disappear).

    It should be called as:
        foo = Statusbar('Initial text to display')
    or, for a blank statusbar:
        foo = Statusbar()

    The "widget" attribute is an urwid widget.
    """

    def __init__(self, config, s=None):
        self.config = config
        self.s = s or ''

        # XXX wrap in AttrMap for wrapping?
        self.widget = urwid.Text(('main', self.s))


def format_tokens(tokensource):
    for token, text in tokensource:
        if text == '\n':
            continue

        # TODO: something about inversing Parenthesis
        while token not in theme_map:
            token = token.parent
        yield (theme_map[token], text)


class BPythonEdit(urwid.Edit):

    """Customized editor *very* tightly interwoven with URWIDRepl.

    Changes include:

    - The edit text supports markup, not just the caption.
      This works by calling set_edit_markup from the change event
      as well as whenever markup changes while text does not.

    - The widget can be made readonly, which currently just means
      it is no longer selectable and stops drawing the cursor.

      This is currently a one-way operation, but that is just because
      I only need and test the readwrite->readonly transition.
    """

    def __init__(self, *args, **kwargs):
        self._bpy_text = ''
        self._bpy_attr = []
        self._bpy_selectable = True
        urwid.Edit.__init__(self, *args, **kwargs)

    def make_readonly(self):
        self._bpy_selectable = False
        # This is necessary to prevent the listbox we are in getting
        # fresh cursor coords of None from get_cursor_coords
        # immediately after we go readonly and then getting a cached
        # canvas that still has the cursor set. It spots that
        # inconsistency and raises.
        self._invalidate()

    def set_edit_markup(self, markup):
        """Call this when markup changes but the underlying text does not.

        You should arrange for this to be called from the 'change' signal.
        """
        self._bpy_text, self._bpy_attr = urwid.decompose_tagmarkup(markup)
        # This is redundant when we're called off the 'change' signal.
        # I'm assuming this is cheap, making that ok.
        self._invalidate()

    def get_text(self):
        return self._caption + self._bpy_text, self._attrib + self._bpy_attr

    def selectable(self):
        return self._bpy_selectable

    def get_cursor_coords(self, *args, **kwargs):
        # urwid gets confused if a nonselectable widget has a cursor position.
        if not self._bpy_selectable:
            return None
        return urwid.Edit.get_cursor_coords(self, *args, **kwargs)

    def render(self, size, focus=False):
        # XXX I do not want to have to do this, but listbox gets confused
        # if I do not (getting None out of get_cursor_coords because
        # we just became unselectable, then having this render a cursor)
        if not self._bpy_selectable:
            focus = False
        return urwid.Edit.render(self, size, focus=focus)

    def get_pref_col(self, size):
        # Need to make this deal with us being nonselectable
        if not self._bpy_selectable:
            return 'left'
        return urwid.Edit.get_pref_col(self, size)


class Tooltip(urwid.Overlay):

    """Exactly like Overlay but passes events to the bottom window.

    Also uses the cursor position from the bottom window
    (even if this cursor ends up on top of the top window!)

    This is a quick and dirty hack.
    """

    # TODO: mouse events
    def selectable(self):
        return self.bottom_w.selectable()

    def keypress(self, size, key):
        # XXX is just passing size along correct?
        return self.bottom_w.keypress(size, key)

    def get_cursor_coords(self, size):
        return self.bottom_w.get_cursor_coords(size)

    def render(self, size, focus=False):
        canvas = urwid.Overlay.render(self, size, focus)
        # XXX HACK: re-render the bottom and steal its cursor coords
        bottom_c = self.bottom_w.render(size, focus)
        canvas = urwid.CompositeCanvas(canvas)
        canvas.cursor = bottom_c.cursor
        return canvas


class URWIDRepl(repl.Repl):

    # XXX this is getting silly, need to split this up somehow
    def __init__(self, main_loop, frame, listbox, overlay, tooltip,
                 interpreter, statusbar, config):
        repl.Repl.__init__(self, interpreter, config)
        self.main_loop = main_loop
        self.frame = frame
        self.listbox = listbox
        self.overlay = overlay
        self.tooltip = tooltip
        self.edits = []
        self.edit = None
        self.statusbar = statusbar
        # XXX repl.Repl uses this? What is it?
        self.cpos = 0

    # Subclasses of Repl need to implement echo, current_line, cw
    def echo(self, s):
        s = s.rstrip('\n')
        if s:
            text = urwid.Text(('output', s))
            if self.edit is None:
                self.listbox.body.append(text)
            else:
                self.listbox.body.insert(-1, text)
                # The edit widget should be focused and *stay* focused.
                # XXX TODO: make sure the cursor stays in the same spot.
                self.listbox.set_focus(len(self.listbox.body) - 1)
        # TODO: maybe do the redraw after a short delay
        # (for performance)
        self.main_loop.draw_screen()

    def current_line(self):
        """Return the current line (the one the cursor is in)."""
        if self.edit is None:
            return ''
        return self.edit.get_edit_text()

    def cw(self):
        """Return the current word (incomplete word left of cursor)."""
        if self.edit is None:
            return

        pos = self.edit.edit_pos
        text = self.edit.get_edit_text()
        if pos != len(text):
            # Disable autocomplete if not at end of line, like cli does.
            return

        # Stolen from cli. TODO: clean up and split out.
        if (not text or
            (not text[-1].isalnum() and text[-1] not in ('.', '_'))):
            return

        # Seek backwards in text for the first non-identifier char:
        for i, c in enumerate(reversed(text)):
            if not c.isalnum() and c not in ('.', '_'):
                break
        else:
            # No non-identifiers, return everything.
            return text
        # Return everything to the right of the non-identifier.
        return text[-i:]

    def _populate_completion(self, main_loop, user_data):
        widget_list = self.tooltip.body
        widget_list[1] = urwid.Text('')
        # This is just me flailing around wildly. TODO: actually write.
        if self.complete():
            if self.argspec:
                text = repr(self.argspec)
            else:
                text = ''
            if self.matches:
                texts = [urwid.Text(('main', match))
                         for match in self.matches]
                width = max(text.pack()[0] for text in texts)
                gridflow = urwid.GridFlow(texts, width, 1, 0, 'left')
                widget_list[1] = gridflow
            widget_list[0].set_text(text)
            self.frame.body = self.overlay
        else:
            self.frame.body = self.listbox

    def reprint_line(self, lineno, tokens):
        edit = self.edits[-len(self.buffer) + lineno - 1]
        edit.set_edit_markup(list(format_tokens(tokens)))

    def push(self, s, insert_into_history=True):
        # Pretty blindly adapted from bpython.cli
        try:
            return repl.Repl.push(self, s, insert_into_history)
        except SystemExit:
            raise urwid.ExitMainLoop()

    def start(self):
        # Stolen from bpython.cli again
        self.push('from bpython._internal import _help as help\n', False)
        self.prompt(False)

    def prompt(self, more):
        # XXX what is s_hist?
        if not more:
            self.edit = BPythonEdit(caption=('prompt', '>>> '))
            self.stdout_hist += '>>> '
        else:
            self.edit = BPythonEdit(caption=('prompt_more', '... '))
            self.stdout_hist += '... '

        urwid.connect_signal(self.edit, 'change', self.on_input_change)
        self.edits.append(self.edit)
        self.listbox.body.append(self.edit)
        self.listbox.set_focus(len(self.listbox.body) - 1)
        # Hide the tooltip
        self.frame.body = self.listbox

    def on_input_change(self, edit, text):
        tokens = self.tokenize(text, False)
        edit.set_edit_markup(list(format_tokens(tokens)))
        # If we call this synchronously the get_edit_text() in repl.cw
        # still returns the old text...
        self.main_loop.set_alarm_in(0, self._populate_completion)
        self._reposition_tooltip()

    def _reposition_tooltip(self):
        # Reposition the tooltip based on cursor position.
        screen_cols, screen_rows = self.main_loop.screen.get_cols_rows()
        # XXX this should use self.listbox.get_cursor_coords
        # but that doesn't exist (urwid oversight)
        offset, inset = self.listbox.get_focus_offset_inset(
            (screen_cols, screen_rows))
        rel_x, rel_y = self.edit.get_cursor_coords((screen_cols,))
        y = offset + rel_y
        if y < 0:
            # Cursor off the screen (no clue if this can happen).
            # Just clamp to 0.
            y = 0

        # XXX the tooltip is displayed way too huge now. The easiest way
        # to fix that is probably to figure out how much size the
        # listbox actually needs here and adjust height_amount.

        # XXX not sure if these overlay attributes are meant to be public...
        if y * 2 < screen_rows:
            self.overlay.valign_type = 'fixed top'
            self.overlay.valign_amount = y + 1
            self.overlay.height_type = 'fixed bottom'
            self.overlay.height_amount = 0
        else:
            self.overlay.valign_type = 'fixed bottom'
            self.overlay.valign_amount = screen_rows - y - 1
            self.overlay.height_type = 'fixed top'
            self.overlay.height_amount = 0

    def handle_input(self, event):
        if event == 'enter':
            inp = self.edit.get_edit_text()
            self.history.append(inp)
            self.edit.make_readonly()
            # XXX what is this s_hist thing?
            self.stdout_hist += inp + '\n'
            self.edit = None
            more = self.push(inp)
            self.prompt(more)


def main(args=None, locals_=None, banner=None):
    # Err, somewhat redundant. There is a call to this buried in urwid.util.
    # That seems unfortunate though, so assume that's going away...
    locale.setlocale(locale.LC_ALL, '')

    # TODO: maybe support displays other than raw_display?
    config, options, exec_args = bpargs.parse(args, (
            'Urwid options', None, [
                Option('--reactor', '-r',
                       help='Run a reactor (see --help-reactors)'),
                Option('--help-reactors', action='store_true',
                       help='List available reactors for -r'),
                ]))

    if options.help_reactors:
        from twisted.application import reactors
        # Stolen from twisted.application.app (twistd).
        for r in reactors.getReactorTypes():
            print '    %-4s\t%s' % (r.shortName, r.description)
        return

    palette = [
        (name, COLORMAP[color.lower()], 'default',
         'bold' if color.isupper() else 'default')
        for name, color in config.color_scheme.iteritems()]

    if options.reactor:
        from twisted.application import reactors
        try:
            # XXX why does this not just return the reactor it installed?
            reactor = reactors.installReactor(options.reactor)
            if reactor is None:
                from twisted.internet import reactor
        except reactors.NoSuchReactor:
            sys.stderr.write('Reactor %s does not exist\n' % (
                    options.reactor,))
            return
        event_loop = urwid.TwistedEventLoop(reactor)
    else:
        # None, not urwid.SelectEventLoop(), to work with
        # screens that do not support external event loops.
        event_loop = None
    # TODO: there is also a glib event loop. Do we want that one?

    listbox = urwid.ListBox(urwid.SimpleListWalker([]))

    # String is straight from bpython.cli
    statusbar = Statusbar(
        config,
        " <%s> Rewind  <%s> Save  <%s> Pastebin  <%s> Pager  <%s> Show Source " %
        (config.undo_key, config.save_key,
         config.pastebin_key, config.last_output_key,
         config.show_source_key))

    tooltip = urwid.ListBox(urwid.SimpleListWalker([
                urwid.Text(''), urwid.Text('')]))
    # TODO: this linebox should use the 'main' color.
    overlay = Tooltip(urwid.LineBox(tooltip), listbox,
                      'left', ('relative', 100),
                      ('fixed top', 0), ('fixed bottom', 0))

    frame = urwid.Frame(overlay, footer=statusbar.widget)

    # __main__ construction from bpython.cli
    if locals_ is None:
        main_mod = sys.modules['__main__'] = ModuleType('__main__')
        locals_ = main_mod.__dict__
    interpreter = repl.Interpreter(locals_, locale.getpreferredencoding())

    # This constructs a raw_display.Screen, which nabs sys.stdin/out.
    loop = urwid.MainLoop(frame, palette, event_loop=event_loop)

    myrepl = URWIDRepl(loop, frame, listbox, overlay, tooltip,
                       interpreter, statusbar, config)

    # XXX HACK: circular dependency between the event loop and repl.
    # Fix by not using unhandled_input?
    loop._unhandled_input = myrepl.handle_input

    # Save stdin, stdout and stderr for later restoration
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    try:
        # XXX aargh, we have to leave sys.stdin alone for now:
        # urwid.display_common.RealTerminal.tty_signal_keys calls
        # sys.stdin.fileno() instead of getting stdin passed in as
        # raw_display.Screen._term_input_file :(

        # XXX no stdin for you! What to do here?
        #sys.stdin = None #FakeStdin(myrepl)
        sys.stdout = myrepl
        sys.stderr = myrepl

        # This needs more thought. What needs to happen inside the mainloop?
        # Note that we need the mainloop started before our stdio
        # redirection is hit.
        def start(main_loop, user_data):
            if exec_args:
                bpargs.exec_code(interpreter, exec_args)
                if not options.interactive:
                    raise urwid.ExitMainLoop()
            if not exec_args:
                sys.path.insert(0, '')
                # this is CLIRepl.startup inlined.
                filename = os.environ.get('PYTHONSTARTUP')
                if filename and os.path.isfile(filename):
                    with open(filename, 'r') as f:
                        if py3:
                            interpreter.runsource(f.read(), filename, 'exec')
                        else:
                            interpreter.runsource(f.read(), filename, 'exec',
                                                  encode=False)

            if banner is not None:
                repl.write(banner)
                repl.write('\n')
            myrepl.start()

            # This bypasses main_loop.set_alarm_in because we must *not*
            # hit the draw_screen call (it's unnecessary and slow).
            def run_find_coroutine():
                if find_coroutine():
                    main_loop.event_loop.alarm(0, run_find_coroutine)

            run_find_coroutine()

        loop.set_alarm_in(0, start)

        loop.run()

        if config.hist_length:
            histfilename = os.path.expanduser(config.hist_file)
            myrepl.rl_history.save(histfilename,
                                   locale.getpreferredencoding())
    finally:
        sys.stdin = orig_stdin
        sys.stderr = orig_stderr
        sys.stdout = orig_stdout

    if config.flush_output and not options.quiet:
        sys.stdout.write(myrepl.getstdout())
    sys.stdout.flush()


if __name__ == '__main__':
    main()
