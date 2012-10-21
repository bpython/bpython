# The MIT License
#
# Copyright (c) 2009-2011 the bpython authors.
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
#


# This module is called "bpython.gtk_" to avoid name clashes with the
# "original" gtk module. I first had used an absolute_import import from
# the future to avoid that, but people are stupid and add the package path
# to sys.path.

from __future__ import with_statement
import inspect
import optparse
import os
import sys
from locale import getpreferredencoding

import gobject
import gtk
import pango

from bpython import importcompletion, repl, translations
from bpython._py3compat import PythonLexer, py3
from bpython.formatter import theme_map
from bpython.translations import _
import bpython.args


_COLORS = dict(b='blue', c='cyan', g='green', m='magenta', r='red',
               w='white', y='yellow', k='black', d='black')

def add_tags_to_buffer(color_scheme, text_buffer):
    tags = dict()
    for (name, value) in color_scheme.iteritems():
        tag = tags[name] = text_buffer.create_tag(name)
        for (char, prop) in zip(value, ['foreground', 'background']):
            if char.lower() == 'd':
                continue
            tag.set_property(prop, _COLORS[char.lower()])
            if char.isupper():
                tag.set_property('weight', pango.WEIGHT_BOLD)
    return tags

class ArgspecFormatter(object):
    """
    Format an argspec using Pango markup language.
    """

    def format(self, args, varargs, varkw, defaults, in_arg):
        self.args_seen = 0
        self.in_arg = in_arg
        return inspect.formatargspec(args, varargs, varkw, defaults,
                                     self.formatarg,
                                     formatvalue=self.formatvalue)

    def formatarg(self, name):
        if name == self.in_arg or self.args_seen == self.in_arg:
            string = '<b><i>%s</i></b>' % (name, )
        else:
            string = name
        self.args_seen += 1
        return string

    def formatvalue(self, value):
        return '=%r' % (value, )


class ExceptionDialog(gtk.MessageDialog):
    def __init__(self, exc_type, exc_value, tb, text=None):
        if text is None:
            text = _('An error occurred.')
        gtk.MessageDialog.__init__(self, buttons=gtk.BUTTONS_CLOSE,
                                   type=gtk.MESSAGE_ERROR,
                                   message_format=text)
        self.set_resizable(True)
        import cgitb
        text = cgitb.text((exc_type, exc_value, tb), 5)
        expander = gtk.Expander(_('Exception details'))
        self.vbox.pack_start(expander)
        textview = gtk.TextView()
        textview.get_buffer().set_text(text)
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.add(textview)
        expander.add(scrolled_window)
        self.show_all()


class ExceptionManager(object):
    """
    A context manager which runs the dialog `DialogType` on error, with
    the exception's type, value, a traceback and a text to display as
    arguments.
    """
    def __init__(self, DialogType, text=None):
        self.DialogType = DialogType
        self.text = text or _('An error occurred.')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not (exc_value is None or
                issubclass(exc_type, (KeyboardInterrupt, SystemExit))):
            dialog = self.DialogType(exc_type, exc_value, traceback, self.text)
            dialog.run()
            dialog.destroy()

class Nested(object):
    """
    A helper class, inspired by a semaphore.
    """

    def __init__(self):
        self.counter = 0

    def __enter__(self):
        self.counter += 1
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.counter -= 1

    def __nonzero__(self):
        return bool(self.counter)

class Statusbar(gtk.Statusbar):
    """Contains feedback messages"""
    def __init__(self):
        gtk.Statusbar.__init__(self)
        self.context_id = self.get_context_id(_('Statusbar'))

    def message(self, s, n=3):
        self.clear()
        self.push(self.context_id, s)
        gobject.timeout_add(n*1000, self.clear)

    def clear(self):
        self.pop(self.context_id)

        # To stop the timeout from firing again
        return False


class SuggestionWindow(gtk.Window):
    """
    The window where suggestions are displayed.
    """
    __gsignals__ = dict(expose_event=None,
                        selection_changed=(gobject.SIGNAL_RUN_LAST, None,
                                           (str, )))

    def __init__(self):
        gtk.Window.__init__(self, gtk.WINDOW_POPUP)
        self.set_app_paintable(True)
        self.set_border_width(4)
        self.set_decorated(False)
        self.set_name('gtk-tooltips')
        self.argspec_formatter = ArgspecFormatter()

        vbox = gtk.VBox(homogeneous=False)
        vbox.set_style(self.get_style())

        self.argspec_label = gtk.Label()
        self.argspec_label.set_alignment(0, 0)
        self.argspec_label.set_line_wrap(True)
        self.argspec_label.set_use_markup(True)
        vbox.pack_start(self.argspec_label, expand=False)

        self.docstring_label = gtk.Label()
        self.docstring_label.set_alignment(0, 0)
        style = self.docstring_label.get_style()
        #color = _COLORS[self.config.color_scheme['comment'].lower()]
        #color = gtk.gdk.color_parse(color)
        #style.fg[gtk.STATE_NORMAL] = color
        self.docstring_label.set_style(style)
        vbox.pack_start(self.docstring_label, expand=False)

        self.model = gtk.ListStore(str, str)
        self.view = gtk.TreeView(self.model)
        self.view.set_headers_visible(False)
        self.view.set_style(self.get_style())
        column = gtk.TreeViewColumn(None, gtk.CellRendererText(),
                                    text=0, background=1)
        self.view.append_column(column)
        self.view.get_selection().connect('changed', self.on_selection_changed)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.view)
        vbox.pack_start(sw)

        self.add(vbox)
        self.resize(300, 150)
        self.show_all()

    def back(self):
        if len(self.model):
            self.select(-1)

    def do_expose_event(self, event):
        """
        Draw a flat box around the popup window on expose event.
        """
        width, height = self.get_size()
        self.style.paint_flat_box(self.window, gtk.STATE_NORMAL,
                                  gtk.SHADOW_OUT, None, self,
                                  _('tooltip'), 0, 0, width, height)
        gtk.Window.do_expose_event(self, event)

    def forward(self):
        if len(self.model):
            self.select(1)

    def on_selection_changed(self, selection):
        model, iter_ = selection.get_selected()
        if iter_ is not None:
            value = model.get_value(iter_, 0)
            self.emit('selection-changed', value)

    def select(self, offset):
        """
        Select the suggestions at offset `offset`.
        """
        selection = self.view.get_selection()
        model, iter_ = selection.get_selected()
        if iter_ is not None:
            row = model.get_path(iter_)[0]
            row += offset
        else:
            row = 0
        if row < 0:
            row = len(model) - 1
        elif row >= len(model):
            row = 0
        iter_ = model.get_iter(row)
        selection.select_iter(iter_)
        self.view.scroll_to_cell(row)

    def update_argspec(self, argspec):
        if argspec:
            func_name, args, is_bound_method, in_arg = argspec[:4]
            args, varargs, varkw, defaults = args[:4]
            if is_bound_method and isinstance(in_arg, int):
                in_arg += 1

            argspec = self.argspec_formatter.format(args, varargs, varkw,
                                                    defaults, in_arg)
            markup = '<b>%s</b>%s' % (func_name, argspec)
            self.argspec_label.set_markup(markup)
        self.argspec_label.set_property('visible', bool(argspec))

    def update_docstring(self, docstring):
        self.docstring_label.set_text(docstring)
        self.docstring_label.set_property('visible', bool(docstring))

    def update_matches(self, matches):
        self.model.clear()
        bg = self.get_style().bg[gtk.STATE_NORMAL]
        for match in matches:
            self.model.append([match, bg.to_string()])
        self.view.set_property('visible', bool(matches))


class GTKInteraction(repl.Interaction):
    def __init__(self, config, statusbar):
        repl.Interaction.__init__(self, config, statusbar)

    def confirm(self, q):
        dialog = gtk.MessageDialog(None, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
                                   gtk.BUTTONS_YES_NO, q)
        response = dialog.run()
        dialog.destroy()
        return response == gtk.RESPONSE_YES

    def file_prompt(self, s):
        chooser = gtk.FileChooserDialog(title=_("File to save to"),
                                        action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL,
                                                 gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_OPEN,
                                                 gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        chooser.set_current_name('test.py')
        chooser.set_current_folder(os.path.expanduser('~'))

        pyfilter = gtk.FileFilter()
        pyfilter.set_name(_("Python files"))
        pyfilter.add_pattern("*.py")
        chooser.add_filter(pyfilter)

        allfilter = gtk.FileFilter()
        allfilter.set_name(_("All files"))
        allfilter.add_pattern("*")
        chooser.add_filter(allfilter)

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            fn = chooser.get_filename()
        else:
            fn = False

        chooser.destroy()

        return fn

    def notify(self, s, n=10):
        self.statusbar.message(s)

class ReplWidget(gtk.TextView, repl.Repl):
    __gsignals__ = dict(button_press_event=None,
                        focus_in_event=None,
                        focus_out_event=None,
                        realize=None,
                        exit_event=(gobject.SIGNAL_RUN_LAST, None, ()))

    def __init__(self, interpreter, config):
        gtk.TextView.__init__(self)
        repl.Repl.__init__(self, interpreter, config)
        self.interp.writetb = self.writetb
        self.exit_value = ()
        self.editing = Nested()
        self.reset_indent = False
        self.modify_font(pango.FontDescription(self.config.gtk_font))
        self.set_wrap_mode(gtk.WRAP_CHAR)
        self.list_win = SuggestionWindow()
        self.list_win.connect('selection-changed',
                              self.on_suggestion_selection_changed)
        self.list_win.hide()

        self.modify_base('normal', gtk.gdk.color_parse(_COLORS[self.config.color_gtk_scheme['background']]))

        self.text_buffer = self.get_buffer()
        self.interact = GTKInteraction(self.config, Statusbar())
        tags = add_tags_to_buffer(self.config.color_gtk_scheme, self.text_buffer)
        tags['prompt'].set_property('editable', False)

        self.text_buffer.connect('delete-range', self.on_buf_delete_range)
        self.text_buffer.connect('insert-text', self.on_buf_insert_text)
        self.text_buffer.connect('mark-set', self.on_buf_mark_set)

    def change_line(self, line):
        """
        Replace the current input line with `line`.
        """
        with self.editing:
            self.text_buffer.delete(self.get_line_start_iter(),
                                    self.get_line_end_iter())
        if self.config.syntax:
            self.insert_highlighted(self.get_line_start_iter(), line)
        else:
            self.text_buffer.insert(self.get_line_start_iter(), line)

    def clear_current_line(self):
        """
        Called when a SyntaxError occurs.
        """
        repl.Repl.clear_current_line(self)
        self.reset_indent = True

    def complete(self):
        if self.config.auto_display_list:
            self.list_win_visible = repl.Repl.complete(self)
            if self.list_win_visible:
                self.list_win.update_argspec(self.argspec)
                self.list_win.update_docstring(self.docstring or '')
                self.list_win.update_matches(self.matches)

                iter_rect = self.get_iter_location(self.get_cursor_iter())
                x, y = self.window.get_origin()
                _, height = self.get_line_yrange(self.get_cursor_iter())
                self.list_win.move(x + iter_rect.x,
                                   y + iter_rect.y + height)
                self.list_win.show()
            else:
                self.list_win.hide()

    @property
    def cpos(self):
        cpos = (self.get_line_end_iter().get_offset() -
                self.get_cursor_iter().get_offset())
        if cpos and not self.get_overwrite():
            cpos += 1
        return cpos

    def cw(self):
        """
        Return the current word.
        """
        return self.text_buffer.get_text(self.get_word_start_iter(),
                                         self.get_cursor_iter())

    def current_line(self):
        """
        Return the current input line.
        """
        return self.text_buffer.get_slice(self.get_line_start_iter(),
                                          self.get_line_end_iter())

    def echo(self, string):
        with self.editing:
            self.text_buffer.insert_with_tags_by_name(self.get_cursor_iter(),
                                                      string, 'output')
        self.move_cursor(len(string))

    def get_cursor_iter(self):
        """
        Return an iter where the cursor currently is.
        """
        cursor_marker = self.text_buffer.get_insert()
        return self.text_buffer.get_iter_at_mark(cursor_marker)

    def get_line_start_iter(self):
        """
        Return an iter where the current line starts.
        """
        line_start_marker = self.text_buffer.get_mark('line_start')
        if line_start_marker is None:
            return self.text_buffer.get_start_iter()
        return self.text_buffer.get_iter_at_mark(line_start_marker)

    def get_line_end_iter(self):
        """
        Return an iter where the current line ends.
        """
        iter_ = self.get_line_start_iter()
        if not iter_.ends_line() and not iter_.forward_to_line_end():
            iter_ = self.text_buffer.get_end_iter()
        return iter_

    def get_word_start_iter(self):
        iter_ = self.get_cursor_iter()
        pred = lambda char, _: not (char.isalnum() or char in '_.')
        if iter_.backward_find_char(pred, None, self.get_line_start_iter()):
            iter_.forward_char()
        return iter_

    def do_button_press_event(self, event):
        if self.list_win_visible:
            self.list_win.hide()
        return gtk.TextView.do_button_press_event(self, event)

    def do_focus_in_event(self, event):
        if self.list_win_visible:
            self.list_win.show()
        return gtk.TextView.do_focus_in_event(self, event)

    def do_focus_out_event(self, event):
        if self.list_win_visible:
            self.list_win.hide()
        return gtk.TextView.do_focus_out_event(self, event)

    def do_key_press_event(self, event):
        state = event.state & (gtk.gdk.CONTROL_MASK |
                               gtk.gdk.MOD1_MASK |
                               gtk.gdk.MOD4_MASK |
                               gtk.gdk.SHIFT_MASK)
        if not state:
            if event.keyval == gtk.keysyms.F2:
                source = self.get_source_of_current_name()
                if source is not None:
                    show_source_in_new_window(source, self.config.color_gtk_scheme,
                                              self.config.syntax)
                else:
                    self.interact.notify(_('Cannot show source.'))
            elif event.keyval == gtk.keysyms.Return:
                if self.list_win_visible:
                    self.list_win_visible = False
                    self.list_win.hide()
                self.rl_history.reset()
                line = self.current_line()
                more = self.push_line()
                self.prompt(more)
                if self.reset_indent:
                    self.reset_indent = False
                else:
                    indentation = self.next_indentation()
                    if indentation:
                        with self.editing:
                            self.text_buffer.insert(self.get_cursor_iter(),
                                                    '\t' * indentation)
                        self.move_cursor(indentation)
                return True
            elif event.keyval == gtk.keysyms.Tab and self.list_win_visible:
                self.list_win.forward()
                return True
            elif event.keyval == gtk.keysyms.Up:
                if self.list_win_visible:
                    self.list_win.back()
                else:
                    if not self.rl_history.is_at_end:
                        self.rl_history.enter(self.current_line())
                        self.change_line(self.rl_history.back())
                        self.text_buffer.place_cursor(self.get_line_end_iter())
                return True
            elif event.keyval == gtk.keysyms.Down:
                if self.list_win_visible:
                    self.list_win.forward()
                else:
                    if not self.rl_history.is_at_start:
                        self.rl_history.enter(self.current_line())
                        self.change_line(self.rl_history.forward())
                        self.text_buffer.place_cursor(self.get_line_end_iter())
                return True
        elif state & gtk.gdk.SHIFT_MASK:
            if (event.keyval == gtk.keysyms.ISO_Left_Tab and
                self.list_win_visible):
                self.list_win.back()
                return True
        elif state & gtk.gdk.CONTROL_MASK:
            if event.string == chr(4) and not self.current_line():
                self.emit('exit-event')
                return True
        return gtk.TextView.do_key_press_event(self, event)

    def do_realize(self):
        gtk.TextView.do_realize(self)
        self.prompt(False)

    def highlight(self, start_iter, tokens):
        """
        Highlight the text starting at `start_iter` using `tokens`.
        """
        token_start_iter = start_iter.copy()
        token_end_iter = start_iter.copy()
        for (token, value) in tokens:
            while token not in theme_map:
                token = token.parent
            token_end_iter.forward_chars(len(value))
            self.text_buffer.apply_tag_by_name(theme_map[token],
                                               token_start_iter, token_end_iter)
            token_start_iter.forward_chars(len(value))

    def highlight_current_line(self):
        """
        Highlight the current line.
        """
        if self.config.syntax:
            if self.highlighted_paren is not None:
                self.reprint_line(*self.highlighted_paren)
                self.highlighted_paren = None

            start = self.get_line_start_iter()
            self.text_buffer.remove_all_tags(start, self.get_line_end_iter())
            self.highlight(start, self.tokenize(self.current_line()))

    def insert_highlighted(self, iter_, string):
        offset = iter_.get_offset()
        newline = iter_.forward_to_line_end()
        # self.tokenize() may call self.reprint_line(), which will
        # invalidate iters.
        tokens = self.tokenize(string, newline)
        iter_ = self.text_buffer.get_iter_at_offset(offset)
        self.insert_highlighted_tokens(iter_, tokens)

    def insert_highlighted_tokens(self, iter_, tokens):
        offset = iter_.get_offset()
        buffer = self.text_buffer
        for (token, value) in tokens:
            while token not in theme_map:
                token = token.parent
            iter_ = buffer.get_iter_at_offset(offset)
            with self.editing:
                buffer.insert_with_tags_by_name(iter_, value,
                                                theme_map[token])
            offset += len(value)

    def move_cursor(self, offset):
        """
        Move the cursor to a given offset.
        """
        iter_ = self.get_cursor_iter()
        iter_.forward_chars(offset)
        self.text_buffer.place_cursor(iter_)
        return iter_

    def on_buf_delete_range(self, buffer, start, end):
        if self.editing:
            return
        buffer.emit_stop_by_name('delete-range')
        # Only allow editing of the current line and not of previous ones
        line_start = self.get_line_start_iter()
        if end.compare(line_start) < 0:
            return
        elif start.compare(line_start) < 0:
            start = line_start
        with self.editing:
            buffer.delete(start, end)
        self.highlight_current_line()
        self.complete()

    def on_buf_insert_text(self, buffer, iter_, text, length):
        if self.editing:
            return
        self.set_cursor_to_valid_insert_position()
        buffer.emit_stop_by_name('insert-text')
        for (i, line) in enumerate(text.splitlines()):
            if i:
                self.prompt(self.push_line())
            with self.editing:
                buffer.insert_at_cursor(line)
        self.highlight_current_line()
        self.complete()

    def on_buf_mark_set(self, buffer, iter_, textmark):
        if (textmark.get_name() == 'insert' and
            self.get_line_start_iter().compare(iter_) < 0):
            self.highlight_current_line()

    def on_suggestion_selection_changed(self, selection, word):
        with self.editing:
            self.text_buffer.delete(self.get_word_start_iter(),
                                    self.get_cursor_iter())
            self.text_buffer.insert_at_cursor(word)

    def do_paste(self, widget):
        clipboard = gtk.clipboard_get()
        paste_url = self.pastebin()
        if paste_url:
            clipboard.set_text(paste_url)
            clipboard.store()

    def do_write2file(self, widget):
        self.write2file()

    def do_partial_paste(self, widget):
        bounds = self.text_buffer.get_selection_bounds()
        if bounds == ():
            # FIXME show a nice status bar message
            pass
        else:
            self.pastebin(self.text_buffer.get_text(bounds[0], bounds[1]))

    def write(self, s):
        """For overriding stdout defaults"""
        if '\x04' in s:
            for block in s.split('\x04'):
                self.write(block)
            return
        if s.rstrip() and '\x03' in s:
            t = s.split('\x03')[1]
        else:
            t = s

        if not py3 and isinstance(t, unicode):
            t = t.encode(getpreferredencoding())

        self.echo(s)
        self.s_hist.append(s.rstrip())

    def prompt(self, more):
        """
        Show the appropriate Python prompt.
        """
        if more:
            text = self.ps2
        else:
            text = self.ps1
        with self.editing:
            iter_ = self.get_cursor_iter()
            self.text_buffer.insert_with_tags_by_name(iter_, text, 'prompt')
        iter_.forward_chars(len(text))
        mark = self.text_buffer.create_mark('line_start', iter_, True)
        self.text_buffer.place_cursor(iter_)
        self.scroll_to_mark(mark, 0.2)

    def push_line(self):
        line = self.current_line()
        # Save mark for easy referencing later
        self.text_buffer.create_mark('line%i_start' % (len(self.buffer), ),
                                     self.get_line_start_iter(), True)
        iter_ = self.get_line_end_iter()
        self.text_buffer.place_cursor(iter_)
        with self.editing:
            self.text_buffer.insert(iter_, '\n')
        self.move_cursor(1)
        self.highlight_current_line()
        try:
            return self.push(line + '\n')
        except SystemExit, e:
            self.exit_value = e.args
            self.emit('exit-event')
            return False

    def reprint_line(self, lineno, tokens):
        """
        Helper function for paren highlighting: Reprint line at offset
        `lineno` in current input buffer.
        """
        if not self.buffer or lineno == len(self.buffer):
            return

        mark = self.text_buffer.get_mark('line%i_start' % (lineno, ))
        start = self.text_buffer.get_iter_at_mark(mark)
        end = start.copy()
        end.forward_to_line_end()
        self.text_buffer.remove_all_tags(start, end)
        self.highlight(start, tokens)

    def set_cursor_to_valid_insert_position(self):
        cursor_iter = self.get_cursor_iter()
        line_start_iter = self.get_line_start_iter()
        if line_start_iter.compare(cursor_iter) > 0:
            self.text_buffer.place_cursor(line_start_iter)

    def getstdout(self):
        bounds = self.text_buffer.get_bounds()
        text = self.text_buffer.get_text(bounds[0], bounds[1])
        return text

    def writetb(self, lines):
        with ExceptionManager(ExceptionDialog,
                              'An error occured while trying to display '
                              'an error. Please contact the bpython '
                              'developers.'):
            string = ''.join(lines)
            with self.editing:
                self.text_buffer.insert_with_tags_by_name(
                    self.get_cursor_iter(), string, 'error'
                )
            self.move_cursor(len(string))

def show_source_in_new_window(source, color_scheme=None, highlight=True):
    win = gtk.Window()
    sw = gtk.ScrolledWindow()
    view = gtk.TextView()
    buffer = view.get_buffer()
    if highlight:
        add_tags_to_buffer(color_scheme, buffer)
        for (token, value) in PythonLexer().get_tokens(source):
            while token not in theme_map:
                token = token.parent
            iter_ = buffer.get_end_iter()
            buffer.insert_with_tags_by_name(iter_, value, theme_map[token])
    else:
        buffer.insert(buffer.get_end_iter(), source)
    sw.add(view)
    win.add(sw)
    win.show_all()

def init_import_completion():
    try:
        importcompletion.find_iterator.next()
    except StopIteration:
        return False
    else:
        return True


def main(args=None):
    translations.init()

    gtk_options = (_('gtk-specific options'),
                   _("Options specific to bpython's Gtk+ front end"),
                   [optparse.Option('--socket-id', dest='socket_id',
                                    type='int', help=_('Embed bpython'))])
    config, options, exec_args = bpython.args.parse(args, gtk_options,
                                                    True)

    interpreter = repl.Interpreter(None, getpreferredencoding())
    repl_widget = ReplWidget(interpreter, config)
    repl_widget.connect('exit-event', gtk.main_quit)

    gobject.idle_add(init_import_completion)

    if not exec_args:
        sys.path.insert(0, '')
        gobject.idle_add(repl_widget.startup)
    else:
        if options.interactive:
            gobject.idle_add(bpython.args.exec_code, interpreter, exec_args)
        else:
            bpython.args.exec_code(interpreter, exec_args)
            return 0

    sys.stderr = repl_widget
    sys.stdout = repl_widget

    if not options.socket_id:
        parent = gtk.Window()
        parent.connect('delete-event', lambda widget, event: gtk.main_quit())

        # branding
        # fix icon to be distributed and loaded from the correct path
        icon = gtk.gdk.pixbuf_new_from_file(os.path.join(os.path.dirname(__file__),
                                                         'logo.png'))

        parent.set_title('bpython')
        parent.set_icon(icon)
        parent.resize(600, 300)
    else:
        parent = gtk.Plug(options.socket_id)
        parent.connect('destroy', gtk.main_quit)

    container = gtk.VBox()
    parent.add(container)

    mb = gtk.MenuBar()
    filemenu = gtk.Menu()

    filem = gtk.MenuItem("File")
    filem.set_submenu(filemenu)

    save = gtk.ImageMenuItem(gtk.STOCK_SAVE)
    save.connect("activate", repl_widget.do_write2file)
    filemenu.append(save)

    pastebin = gtk.MenuItem("Pastebin")
    pastebin.connect("activate", repl_widget.do_paste)
    filemenu.append(pastebin)

    pastebin_partial = gtk.MenuItem(_("Pastebin selection"))
    pastebin_partial.connect("activate", repl_widget.do_partial_paste)
    filemenu.append(pastebin_partial)

    exit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
    exit.connect("activate", gtk.main_quit)
    filemenu.append(exit)

    mb.append(filem)
    vbox = gtk.VBox(False, 2)
    vbox.pack_start(mb, False, False, 0)

    container.pack_start(vbox, expand=False)

    # read from config
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    sw.add(repl_widget)
    container.add(sw)

    sb = repl_widget.interact.statusbar
    container.pack_end(sb, expand=False)

    parent.set_focus(repl_widget)
    parent.show_all()
    parent.connect('delete-event', lambda widget, event: gtk.main_quit())

    try:
        gtk.main()
    except KeyboardInterrupt:
        pass

    return repl.extract_exit_value(repl_widget.exit_value)

if __name__ == '__main__':
    from bpython.gtk_ import main
    sys.exit(main())
