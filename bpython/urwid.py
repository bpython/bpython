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
import signal
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


try:
    from twisted.internet import protocol
    from twisted.protocols import basic
except ImportError:
    pass
else:

    class EvalProtocol(basic.LineOnlyReceiver):

        delimiter = '\n'

        def __init__(self, myrepl):
            self.repl = myrepl

        def lineReceived(self, line):
            # HACK!
            # TODO: deal with encoding issues here...
            self.repl.main_loop.process_input(line)
            self.repl.main_loop.process_input(['enter'])


    class EvalFactory(protocol.ServerFactory):

        def __init__(self, myrepl):
            self.repl = myrepl

        def buildProtocol(self, addr):
            return EvalProtocol(self.repl)


class TwistedEventLoop(urwid.TwistedEventLoop):

    """TwistedEventLoop modified to properly stop the reactor.

    urwid 0.9.9 and 0.9.9.1 crash the reactor on ExitMainLoop instead
    of stopping it. One obvious way this breaks is if anything used
    the reactor's thread pool: that thread pool is not shut down if
    the reactor is not stopped, which means python hangs on exit
    (joining the non-daemon threadpool threads that never exit). And
    the default resolver is the ThreadedResolver, so if we looked up
    any names we hang on exit. That is bad enough that we hack up
    urwid a bit here to exit properly.
    """

    def handle_exit(self, f):
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except urwid.ExitMainLoop:
                # This is our change.
                self.reactor.stop()
            except:
                # This is the same as in urwid.
                # We are obviously not supposed to ever hit this.
                import sys
                print sys.exc_info()
                self._exc_info = sys.exc_info()
                self.reactor.crash()
        return wrapper


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

def decoding_input_filter(keys, raw):
    """Input filter for urwid which decodes each key with the locale's
    preferred encoding.'"""
    encoding = locale.getpreferredencoding()
    converted_keys = list()
    for key in keys:
        if isinstance(keys, basestring):
            converted_keys.append(key.decode(encoding))
        else:
            converted_keys.append(key)
    return converted_keys

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

    - move_cursor_to_coords is ignored
      (except for internal calls from keypress or mouse_event).

    - arrow up/down are ignored.

    - an "edit-pos-changed" signal is emitted when edit_pos changes.
    """

    signals = ['edit-pos-changed']

    def __init__(self, tab_length, *args, **kwargs):
        self._bpy_text = ''
        self._bpy_attr = []
        self._bpy_selectable = True
        self._bpy_may_move_cursor = False
        self.tab_length = tab_length
        urwid.Edit.__init__(self, *args, **kwargs)

    def set_edit_pos(self, pos):
        urwid.Edit.set_edit_pos(self, pos)
        self._emit("edit-pos-changed", self.edit_pos)

    def get_edit_pos(self):
        return self._edit_pos

    edit_pos = property(get_edit_pos, set_edit_pos)

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

    def move_cursor_to_coords(self, *args):
        if self._bpy_may_move_cursor:
            return urwid.Edit.move_cursor_to_coords(self, *args)
        return False

    def keypress(self, size, key):
        self._bpy_may_move_cursor = True
        try:
            # Do not handle up/down arrow, leave them for the repl.
            if urwid.command_map[key] in ('cursor up', 'cursor down'):
                return key
            elif key == 'backspace':
                line = self.get_edit_text()
                cpos = len(line) - self.edit_pos
                if not (cpos or len(line) % self.tab_length or line.strip()):
                    self.set_edit_text(line[:-self.tab_length])
                    return None
            return urwid.Edit.keypress(self, size, key)
        finally:
            self._bpy_may_move_cursor = False

    def mouse_event(self, *args):
        self._bpy_may_move_cursor = True
        try:
            return urwid.Edit.mouse_event(self, *args)
        finally:
            self._bpy_may_move_cursor = False


class Tooltip(urwid.BoxWidget):

    """Container inspired by Overlay to position our tooltip.

    bottom_w should be a BoxWidget.
    The top window currently has to be a listbox to support shrinkwrapping.

    This passes keyboard events to the bottom instead of the top window.

    It also positions the top window relative to the cursor position
    from the bottom window and hides it if there is no cursor.
    """

    def __init__(self, bottom_w, listbox):
        self.__super.__init__()

        self.bottom_w = bottom_w
        self.listbox = listbox
        # TODO: this linebox should use the 'main' color.
        self.top_w = urwid.LineBox(listbox)
        self.tooltip_focus = False

    def selectable(self):
        return self.bottom_w.selectable()

    def keypress(self, size, key):
        return self.bottom_w.keypress(size, key)

    def mouse_event(self, size, event, button, col, row, focus):
        # TODO: pass to top widget if visible and inside it.
        if not hasattr(self.bottom_w, 'mouse_event'):
            return False

        return self.bottom_w.mouse_event(
            size, event, button, col, row, focus)

    def get_cursor_coords(self, size):
        return self.bottom_w.get_cursor_coords(size)

    def render(self, size, focus=False):
        maxcol, maxrow = size
        bottom_c = self.bottom_w.render(size, focus)
        cursor = bottom_c.cursor
        if not cursor:
            # Hide the tooltip if there is no cursor.
            return bottom_c

        cursor_x, cursor_y = cursor
        if cursor_y * 2 < maxrow:
            # Cursor is in the top half. Tooltip goes below it:
            y = cursor_y + 1
            rows = maxrow - y
        else:
            # Cursor is in the bottom half. Tooltip fills the area above:
            y = 0
            rows = cursor_y

        # HACK: shrink-wrap the tooltip. This is ugly in multiple ways:
        # - It only works on a listbox.
        # - It assumes the wrapping LineBox eats one char on each edge.
        # - It is a loop.
        #   (ideally it would check how much free space there is,
        #   instead of repeatedly trying smaller sizes)
        while 'bottom' in self.listbox.ends_visible((maxcol - 2, rows - 3)):
            rows -= 1

        # If we're displaying above the cursor move the top edge down:
        if not y:
            y = cursor_y - rows

        # Render *both* windows focused. This is probably not normal in urwid,
        # but it works nicely.
        top_c = self.top_w.render((maxcol, rows),
                                  focus and self.tooltip_focus)

        combi_c = urwid.CanvasOverlay(top_c, bottom_c, 0, y)
        # Use the cursor coordinates from the bottom canvas.
        canvas = urwid.CompositeCanvas(combi_c)
        canvas.cursor = cursor
        return canvas


class URWIDRepl(repl.Repl):

    def __init__(self, event_loop, palette, interpreter, config):
        repl.Repl.__init__(self, interpreter, config)

        self.listbox = urwid.ListBox(urwid.SimpleListWalker([]))

        # String is straight from bpython.cli
        self.statusbar = Statusbar(
            config,
            " <%s> Rewind  <%s> Save  <%s> Pastebin  <%s> Pager  <%s> Show Source " %
            (config.undo_key, config.save_key,
             config.pastebin_key, config.last_output_key,
             config.show_source_key))

        self.tooltip = urwid.ListBox(urwid.SimpleListWalker([]))
        self.tooltip.grid = None
        self.overlay = Tooltip(self.listbox, self.tooltip)

        self.frame = urwid.Frame(self.overlay, footer=self.statusbar.widget)

        if urwid.get_encoding_mode() == 'narrow':
            input_filter = decoding_input_filter
        else:
            input_filter = None

        # This constructs a raw_display.Screen, which nabs sys.stdin/out.
        self.main_loop = urwid.MainLoop(
            self.frame, palette,
            event_loop=event_loop, unhandled_input=self.handle_input,
            input_filter=input_filter)

        self.edits = []
        self.edit = None
        self._completion_update_suppressed = False

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

    @property
    def cpos(self):
        if self.edit is not None:
            return len(self.current_line()) - self.edit.edit_pos
        return 0

    def _populate_completion(self):
        widget_list = self.tooltip.body
        while widget_list:
            widget_list.pop()
        # This is just me flailing around wildly. TODO: actually write.
        if self.complete():
            if self.argspec:
                # This is mostly just stolen from the cli module.
                func_name, args, is_bound, in_arg = self.argspec
                args, varargs, varkw, defaults = args[:4]
                if py3:
                    kwonly, kwonly_defaults = args[4:]
                else:
                    kwonly, kwonly_defaults = [], {}
                markup = [('bold name', func_name),
                          ('name', ': (')]

                # the isinstance checks if we're in a positional arg
                # (instead of a keyword arg), I think
                if is_bound and isinstance(in_arg, int):
                    in_arg += 1

                # bpython.cli checks if this goes off the edge and
                # does clever wrapping. I do not (yet).
                for k, i in enumerate(args):
                    if defaults and k + 1 > len(args) - len(defaults):
                        kw = str(defaults[k - (len(args) - len(defaults))])
                    else:
                        kw = None

                    if not k and str(i) == 'self':
                        color = 'name'
                    else:
                        color = 'token'

                    if k == in_arg or i == in_arg:
                        color = 'bold ' + color

                    markup.append((color, str(i)))
                    if kw:
                        markup.extend([('punctuation', '='),
                                       ('token', kw)])
                    if k != len(args) - 1:
                        markup.append(('punctuation', ', '))

                if varargs:
                    if args:
                        markup.append(('punctuation', ', '))
                    markup.append(('token', '*' + varargs))

                if kwonly:
                    if not varargs:
                        if args:
                            markup.append(('punctuation', ', '))
                        markup.append(('punctuation', '*'))
                    for arg in kwonly:
                        if arg == in_arg:
                            color = 'bold token'
                        else:
                            color = 'token'
                        markup.extend([('punctuation', ', '),
                                       (color, arg)])
                        if arg in kwonly_defaults:
                            markup.extend([('punctuation', '='),
                                           ('token', kwonly_defaults[arg])])

                if varkw:
                    if args or varargs or kwonly:
                        markup.append(('punctuation', ', '))
                    markup.append(('token', '**' + varkw))
                markup.append(('punctuation', ')'))
                widget_list.append(urwid.Text(markup))
            if self.matches:
                attr_map = {}
                focus_map = {'main': 'operator'}
                texts = [urwid.AttrMap(urwid.Text(('main', match)),
                                       attr_map, focus_map)
                         for match in self.matches]
                width = max(text.original_widget.pack()[0] for text in texts)
                gridflow = urwid.GridFlow(texts, width, 1, 0, 'left')
                widget_list.append(gridflow)
                self.tooltip.grid = gridflow
                self.overlay.tooltip_focus = False
            else:
                self.tooltip.grid = None
            self.frame.body = self.overlay
        else:
            self.frame.body = self.listbox
            self.tooltip.grid = None

        if self.docstring:
            # TODO: use self.format_docstring? needs a width/height...
            docstring = self.docstring
            widget_list.append(urwid.Text(('comment', docstring)))

    def reprint_line(self, lineno, tokens):
        edit = self.edits[-len(self.buffer) + lineno - 1]
        edit.set_edit_markup(list(format_tokens(tokens)))

    def push(self, s, insert_into_history=True):
        # Restore the original SIGINT handler. This is needed to be able
        # to break out of infinite loops. If the interpreter itself
        # sees this it prints 'KeyboardInterrupt' and returns (good).
        orig_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        # Pretty blindly adapted from bpython.cli
        try:
            return repl.Repl.push(self, s, insert_into_history)
        except SystemExit:
            raise urwid.ExitMainLoop()
        except KeyboardInterrupt:
            # KeyboardInterrupt happened between the except block around
            # user code execution and this code. This should be rare,
            # but make sure to not kill bpython here, so leaning on
            # ctrl+c to kill buggy code running inside bpython is safe.
            self.keyboard_interrupt()
        finally:
            signal.signal(signal.SIGINT, orig_handler)

    def start(self):
        # Stolen from bpython.cli again
        self.push('from bpython._internal import _help as help\n', False)
        self.prompt(False)

    def keyboard_interrupt(self):
        # Do we need to do more here? Break out of multiline input perhaps?
        self.echo('KeyboardInterrupt')

    def prompt(self, more):
        # XXX is this the right place?
        self.rl_history.reset()
        # XXX what is s_hist?
        if not more:
            self.edit = BPythonEdit(self.config.tab_length,
                                    caption=('prompt', '>>> '))
            self.stdout_hist += '>>> '
        else:
            self.edit = BPythonEdit(self.config.tab_length,
                                    caption=('prompt_more', '... '))
            self.stdout_hist += '... '

        urwid.connect_signal(self.edit, 'change', self.on_input_change)
        urwid.connect_signal(self.edit, 'edit-pos-changed',
                             self.on_edit_pos_changed)
        # Do this after connecting the change signal handler:
        self.edit.insert_text(4 * self.next_indentation() * ' ')
        self.edits.append(self.edit)
        self.listbox.body.append(self.edit)
        self.listbox.set_focus(len(self.listbox.body) - 1)
        # Hide the tooltip
        self.frame.body = self.listbox

    def on_input_change(self, edit, text):
        # TODO: we get very confused here if "text" contains newlines,
        # so we cannot put our edit widget in multiline mode yet.
        # That is probably fixable...
        tokens = self.tokenize(text, False)
        edit.set_edit_markup(list(format_tokens(tokens)))
        if not self._completion_update_suppressed:
            # If we call this synchronously the get_edit_text() in repl.cw
            # still returns the old text...
            self.main_loop.set_alarm_in(
                0, lambda *args: self._populate_completion())

    def on_edit_pos_changed(self, edit, position):
        """Gets called when the cursor position inside the edit changed.
        Rehighlight the current line because there might be a paren under
        the cursor now."""
        tokens = self.tokenize(self.current_line(), False)
        edit.set_edit_markup(list(format_tokens(tokens)))

    def handle_input(self, event):
        if event == 'enter':
            inp = self.edit.get_edit_text()
            self.history.append(inp)
            self.edit.make_readonly()
            # XXX what is this s_hist thing?
            self.stdout_hist += inp.encode(locale.getpreferredencoding()) + '\n'
            self.edit = None
            # This may take a while, so force a redraw first:
            self.main_loop.draw_screen()
            more = self.push(inp)
            self.prompt(more)
        elif event == 'ctrl d':
            # ctrl+d on an empty line exits, otherwise deletes
            if self.edit is not None:
                if not self.edit.get_edit_text():
                    raise urwid.ExitMainLoop()
                else:
                    self.main_loop.process_input(['delete'])
        elif urwid.command_map[event] == 'cursor up':
            # "back" from bpython.cli
            self.rl_history.enter(self.edit.get_edit_text())
            self.edit.set_edit_text('')
            self.edit.insert_text(self.rl_history.back())
        elif urwid.command_map[event] == 'cursor down':
            # "fwd" from bpython.cli
            self.rl_history.enter(self.edit.get_edit_text())
            self.edit.set_edit_text('')
            self.edit.insert_text(self.rl_history.forward())
        elif urwid.command_map[event] == 'next selectable':
            self.tab()
        elif urwid.command_map[event] == 'prev selectable':
            self.tab(True)
        #else:
        #    self.echo(repr(event))

    def tab(self, back=False):
        """Process the tab key being hit.

        If the line is blank or has only whitespace: indent.

        If there is text before the cursor: cycle completions.

        If `back` is True cycle backwards through completions, and return
        instead of indenting.

        Returns True if the key was handled.
        """
        self._completion_update_suppressed = True
        try:
            # Heavily inspired by cli's tab.
            text = self.edit.get_edit_text()
            if not text.lstrip() and not back:
                x_pos = len(text) - self.cpos
                num_spaces = x_pos % self.config.tab_length
                if not num_spaces:
                    num_spaces = self.config.tab_length

                self.edit.insert_text(' ' * num_spaces)
                return True

            if not self.matches_iter:
                self.complete(tab=True)
                cw = self.current_string() or self.cw()
                if not cw:
                    return True
            else:
                cw = self.matches_iter.current_word

            b = os.path.commonprefix(self.matches)
            if b:
                insert = b[len(cw):]
                self.edit.insert_text(insert)
                expanded = bool(insert)
                if expanded:
                    self.matches_iter.update(b, self.matches)
            else:
                expanded = False

            if not expanded and self.matches:
                if self.matches_iter:
                    self.edit.set_edit_text(
                        text[:-len(self.matches_iter.current())] + cw)
                if back:
                    current_match = self.matches_iter.previous()
                else:
                    current_match = self.matches_iter.next()
                if current_match:
                    self.overlay.tooltip_focus = True
                    if self.tooltip.grid:
                        self.tooltip.grid.set_focus(self.matches_iter.index)
                    self.edit.insert_text(current_match[len(cw):])
            return True
        finally:
            self._completion_update_suppressed = False

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
                Option('--plugin', '-p',
                       help='twistd plugin to run (use twistd for a list). '
                       'Use "--" to pass further options to the plugin.'),
                Option('--server', '-s', type='int',
                       help='Port to run an eval server on (forces Twisted)'),
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
    palette.extend([
            ('bold ' + name, color + ',bold', background, monochrome)
            for name, color, background, monochrome in palette])

    if (options.server or options.plugin) and not options.reactor:
        options.reactor = 'select'

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
        event_loop = TwistedEventLoop(reactor)
    else:
        # None, not urwid.SelectEventLoop(), to work with
        # screens that do not support external event loops.
        event_loop = None
    # TODO: there is also a glib event loop. Do we want that one?

    # __main__ construction from bpython.cli
    if locals_ is None:
        main_mod = sys.modules['__main__'] = ModuleType('__main__')
        locals_ = main_mod.__dict__

    if options.plugin:
        from twisted import plugin
        from twisted.application import service
        for plug in plugin.getPlugins(service.IServiceMaker):
            if plug.tapname == options.plugin:
                break
        else:
            sys.stderr.write('Plugin %s does not exist\n' % (options.plugin,))
            return
        plugopts = plug.options()
        plugopts.parseOptions(exec_args)
        serv = plug.makeService(plugopts)
        locals_['service'] = serv
        reactor.callWhenRunning(serv.startService)
        exec_args = []
    interpreter = repl.Interpreter(locals_, locale.getpreferredencoding())

    # This nabs sys.stdin/out via urwid.MainLoop
    myrepl = URWIDRepl(event_loop, palette, interpreter, config)

    if options.server:
        factory = EvalFactory(myrepl)
        reactor.listenTCP(options.server, factory, interface='127.0.0.1')

    if options.reactor:
        # Twisted sets a sigInt handler that stops the reactor unless
        # it sees a different custom signal handler.
        def sigint(*args):
            reactor.callFromThread(myrepl.keyboard_interrupt)
        signal.signal(signal.SIGINT, sigint)

    # Save stdin, stdout and stderr for later restoration
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    # urwid's screen start() and stop() calls currently hit sys.stdin
    # directly (via RealTerminal.tty_signal_keys), so start the screen
    # before swapping sys.std*, and swap them back before restoring
    # the screen. This also avoids crashes if our redirected sys.std*
    # are called before we get around to starting the mainloop
    # (urwid raises an exception if we try to draw to the screen
    # before starting it).
    def run_with_screen_before_mainloop():
        try:
            # Currently we just set this to None because I do not
            # expect code hitting stdin to work. For example: exit()
            # (not sys.exit, site.py's exit) tries to close sys.stdin,
            # which breaks urwid's shutdown. bpython.cli sets this to
            # a fake object that reads input through curses and
            # returns it. When using twisted I do not think we can do
            # that because sys.stdin.read and friends block, and we
            # cannot re-enter the reactor. If using urwid's own
            # mainloop we *might* be able to do something similar and
            # re-enter its mainloop.
            sys.stdin = None #FakeStdin(myrepl)
            sys.stdout = myrepl
            sys.stderr = myrepl

            myrepl.main_loop.set_alarm_in(0, start)

            while True:
                try:
                    myrepl.main_loop.run()
                except KeyboardInterrupt:
                    # HACK: if we run under a twisted mainloop this should
                    # never happen: we have a SIGINT handler set.
                    # If we use the urwid select-based loop we just restart
                    # that loop if interrupted, instead of trying to cook
                    # up an equivalent to reactor.callFromThread (which
                    # is what our Twisted sigint handler does)
                    myrepl.main_loop.set_alarm_in(
                        0, lambda *args: myrepl.keyboard_interrupt())
                    continue
                break

            if config.hist_length:
                histfilename = os.path.expanduser(config.hist_file)
                myrepl.rl_history.save(histfilename,
                                       locale.getpreferredencoding())

        finally:
            sys.stdin = orig_stdin
            sys.stderr = orig_stderr
            sys.stdout = orig_stdout

    # This needs more thought. What needs to happen inside the mainloop?
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

    myrepl.main_loop.screen.run_wrapper(run_with_screen_before_mainloop)

    if config.flush_output and not options.quiet:
        sys.stdout.write(myrepl.getstdout())
    sys.stdout.flush()


if __name__ == '__main__':
    main()
