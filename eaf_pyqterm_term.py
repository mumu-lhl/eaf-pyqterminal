#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2023 Mumulhl
#
# Author:     Mumulhl <mumulhl@duck.com>
# Maintainer: Mumulhl <mumulhl@duck.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re

from core.utils import *
from playsound import playsound
from pyte.screens import Cursor, HistoryScreen
from pyte.streams import ByteStream

BELL_SOUND_PATH = get_emacs_vars(("eaf-pyqterminal-bell-sound-path",))[0]


def get_regexp(thing):
    if thing == "word":
        return re.compile("[\s,\._()=*\"'\[\]/-]")
    elif thing == "symbol":
        return re.compile("\s")


class QTerminalStream(ByteStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class QTerminalScreen(HistoryScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.is_buffer = False

        self.base = 0
        self.in_history = False

        self.cursor_move_mode = False
        self.virtual_cursor = Cursor(0, 0)
        self.old_cursor = Cursor(0, 0)
        self.old_marker_cursor = Cursor(0, 0)
        self.max_virtual_cursor_x = 0
        self.marker = ()
        self.fake_marker = False
        self.first_move = True

    def absolute_y(self, line_num):
        return self.base + line_num

    @property
    def at_top(self):
        return self.base == 0 and self.virtual_cursor.y == 0

    @property
    def at_bottom(self):
        return (
            not self.in_history
            and self.virtual_cursor.y + 1 == self.get_last_blank_line()
        )

    def bell(self):
        playsound(BELL_SOUND_PATH, False)

    def scroll_up(self, line_num):
        if self.is_buffer:
            return

        if self.base != 0:
            self.in_history = True

        base = self.base - line_num
        old_base = self.base
        self.base = 0 if base < 0 else base

        if self.base != old_base:
            self.dirty.update(range(self.lines))

    def scroll_down(self, line_num):
        if self.is_buffer:
            return

        base = self.base + line_num
        old_base = self.base

        if base >= len(self.history.top):
            base = len(self.history.top)
            self.in_history = False

        self.base = base

        if self.base != old_base:
            self.dirty.update(range(self.lines))

    def scroll_to_begin(self):
        if self.is_buffer:
            return

        self.scroll_up(self.base)
        self.virtual_cursor.x, self.virtual_cursor.y = 0, 0

    def scroll_to_bottom(self):
        if self.is_buffer:
            return

        if self.in_history:
            self.base = len(self.history.top)
            self.in_history = False
            self.dirty.update(range(self.lines))

        self.virtual_cursor.x, self.virtual_cursor.y = (
            self.columns - 1,
            self.get_last_blank_line() - 1,
        )
        self.jump_x(self.virtual_cursor.y)

    def get_line(self, line_num, absolute=False):
        top_length = len(self.history.top)

        if not self.in_history:
            self.base = top_length

        if line_num < 0 and -line_num > top_length:
            return self.buffer[self.lines]

        if absolute:
            history_line_num = line_num
        else:
            history_line_num = self.base + line_num

        if history_line_num <= top_length - 1:
            return self.history.top[history_line_num]
        else:
            return self.buffer[self.base - top_length + line_num]

    def get_cursor(self):
        return self.virtual_cursor if self.cursor_move_mode else self.cursor

    def get_line_display(
        self, line_num, *, in_buffer=False, start=0, end=None, absolute=False
    ):
        if end is None:
            end = self.columns

        line = self.buffer[line_num] if in_buffer else self.get_line(line_num, absolute)
        return "".join(line[x].data for x in range(start, end))

    def get_last_blank_line(self):
        for y in range(self.lines - 1, -1, -1):
            if self.get_line_display(y, in_buffer=True).strip() != "":
                return y + 1

        return 0

    def get_max_x(self, line_num):
        line = self.get_line(line_num)
        if len(line) > 0:
            (x, _) = line.copy().popitem()
            return x + 1
        else:
            return self.columns - 1

    def get_last_space_of_line(self, line_num):
        line = self.get_line(line_num)
        for x in range(self.columns - 1, -1, -1):
            if line[x].data != " ":
                return x + 1

        return 0

    def get_end_x(self, line_num):
        max_x = self.get_max_x(line_num)
        last_space = self.get_last_space_of_line(line_num)
        return min(max_x, last_space)

    # https://github.com/selectel/pyte/blob/a1c089e45b5d0eef0f3450984350254248f02519/pyte/screens.py#L286
    def resize(self, lines=None, columns=None):
        lines = lines or self.lines
        columns = columns or self.columns

        self.dirty.update(range(lines))

        if lines == self.lines and columns == self.columns:
            return  # No changes.

        count = self.lines - lines
        last_blank_line = self.get_last_blank_line()
        if count > 0 and last_blank_line > lines:
            if last_blank_line != self.lines:
                count = last_blank_line - count + 1

            self.cursor.y -= count

            for y in range(self.lines):
                line = self.buffer.pop(y)

                if y >= last_blank_line and last_blank_line != self.lines:
                    continue

                if y < count:
                    self.history.top.append(line)
                else:
                    self.buffer[y - count] = line

        if columns < self.columns:
            for line in self.buffer.values():
                for x in range(columns, self.columns):
                    line.pop(x, None)

        self.lines, self.columns = lines, columns

    def toggle_cursor_move_mode(self):
        self.cursor_move_mode = not self.cursor_move_mode
        self.virtual_cursor.x, self.virtual_cursor.y = self.cursor.x, self.cursor.y
        self.first_move = True
        if self.marker != ():
            self.marker = ()
            self.dirty.update(range(self.lines))

    def jump_x(self, y):
        if self.first_move:
            self.first_move = False
            self.max_virtual_cursor_x = self.virtual_cursor.x

        self.virtual_cursor.x = self.max_virtual_cursor_x

        if self.get_line(self.virtual_cursor.y)[self.virtual_cursor.x].data == " ":
            max_x = self.get_end_x(y)
            if max_x < self.virtual_cursor.x:
                self.virtual_cursor.x = max_x

    def next_line(self):
        y = self.virtual_cursor.y + 1

        if not self.in_history and y == self.get_last_blank_line():
            return

        if y > self.lines - 1:
            self.scroll_down(1)
        else:
            self.virtual_cursor.y = y

        self.jump_x(self.virtual_cursor.y)

    def previous_line(self):
        y = self.virtual_cursor.y - 1

        if y < 0:
            self.scroll_up(1)
        else:
            self.virtual_cursor.y = y

        self.jump_x(self.virtual_cursor.y)

    def next_character(self, num=1):
        x = self.virtual_cursor.x + num
        end_x = self.get_end_x(self.virtual_cursor.y)
        line = self.get_line(self.virtual_cursor.y)

        # Skip two width character
        if line[x].data == "":
            x += 1

        if x > end_x and not self.at_bottom:
            self.virtual_cursor.x = 0
            self.max_virtual_cursor_x = 0
            self.next_line()
        elif x <= end_x:
            self.virtual_cursor.x = x
            self.max_virtual_cursor_x = x

    def previous_character(self, num=1):
        x = self.virtual_cursor.x - num
        end_x = self.get_end_x(self.virtual_cursor.y - 1)
        line = self.get_line(self.virtual_cursor.y)

        # Skip two width character
        if line[x].data == "":
            x -= 1

        if x < 0 and not self.at_top:
            self.virtual_cursor.x = end_x
            self.max_virtual_cursor_x = end_x
            self.previous_line()
        elif x >= 0:
            self.virtual_cursor.x = x
            self.max_virtual_cursor_x = x

    def find(self, y, pattern, start, reverse=False):
        line = self.get_line(y)
        iterator = (
            range(start, -1, -1) if reverse else range(start, self.get_end_x(y) + 1)
        )
        string_match = False

        for column in iterator:
            pattern_match = bool(pattern.match(line[column].data))

            if reverse and column == start - 1 and pattern_match:
                string_match = False

            if string_match and pattern_match:
                return column

            if not pattern_match:
                string_match = True

        return -1

    def next_thing(self, thing, first=True):
        start = self.virtual_cursor.x if first else 0
        x = self.find(self.virtual_cursor.y, get_regexp(thing), start)

        self.move_beginning_of_line()

        if x == -1 and self.at_bottom:
            self.move_end_of_line()
            return

        if x == -1:
            self.next_line()
            self.next_thing(thing, False)
        else:
            self.next_character(x)

    def previous_thing(self, thing, first=True):
        start = (
            self.virtual_cursor.x if first else self.get_end_x(self.virtual_cursor.y)
        )
        x = self.find(self.virtual_cursor.y, get_regexp(thing), start, True)

        if x == -1 and self.at_top:
            self.move_beginning_of_line()
            return

        if x == -1:
            self.previous_line()
            self.move_end_of_line()
            self.previous_thing(thing, False)
        else:
            self.move_beginning_of_line()
            self.next_character(x + 1)

    def move_beginning_of_line(self):
        self.virtual_cursor.x = 0
        self.max_virtual_cursor_x = 0

    def move_end_of_line(self):
        self.virtual_cursor.x = self.get_end_x(self.virtual_cursor.y)
        self.max_virtual_cursor_x = self.virtual_cursor.x

    def toggle_mark(self):
        cursor = self.virtual_cursor
        if self.marker != ():
            (_, old_marker_y) = self.marker
            old_marker_y -= self.base
        else:
            old_marker_y = cursor.y

        if self.marker == (cursor.x, self.absolute_y(cursor.y)) or self.fake_marker:
            self.marker = ()
        else:
            self.marker = (cursor.x, self.absolute_y(cursor.y))

        if old_marker_y == cursor.y:
            self.dirty.add(cursor.y)
        elif old_marker_y > cursor.y:
            self.dirty.update(range(cursor.y, old_marker_y + 1))
        elif old_marker_y < cursor.y:
            self.dirty.update(range(old_marker_y, cursor.y + 1))

    def in_selection(self, x, y):
        if self.marker == ():
            return False

        cursor = self.virtual_cursor

        if self.fake_marker:
            if cursor.x != self.old_cursor.x or cursor.y != self.old_cursor.y:
                self.toggle_mark()
                self.fake_marker = False
                return False
            else:
                cursor = self.old_marker_cursor

        (marker_x, marker_y) = self.marker
        marker_y -= self.base
        end_x = self.get_end_x(y)

        if x >= end_x:
            return False

        if cursor.y < y < marker_y or cursor.y > y > marker_y:
            return True

        in_one_line = cursor.y == marker_y == y
        cursor_at_left = cursor.y < marker_y or (
            cursor.y == marker_y and cursor.x < marker_x
        )

        if cursor_at_left:
            if in_one_line and cursor.x <= x < marker_x:
                return True
            elif not in_one_line and (
                (y == cursor.y and x >= cursor.x) or (y == marker_y and x < marker_x)
            ):
                return True
        else:
            if in_one_line and marker_x <= x < cursor.x:
                return True
            elif not in_one_line and (
                (y == cursor.y and x < cursor.x) or (y == marker_y and x >= marker_x)
            ):
                return True

        return False

    def _copy(self, start, end):
        text = ""

        for y in range(start[1], end[1] + 1):
            start_x = start[0] if y == start[1] else 0
            end_x = end[0] if y == end[1] else self.columns
            text += self.get_line_display(y, start=start_x, end=end_x, absolute=True)

        message_to_emacs("Copy text")
        set_clipboard_text(text)

    def _copy_selection(self):
        if self.marker == ():
            message_to_emacs("Nothing selected")
            return

        cursor = self.virtual_cursor
        cursor_y = self.absolute_y(cursor.y)
        (marker_x, marker_y) = self.marker

        if (cursor_y == marker_y and marker_x < cursor.x) or (marker_y < cursor_y):
            start = (marker_x, marker_y)
            end = (cursor.x, cursor_y)
        elif (cursor_y == marker_y and cursor.x < marker_x) or (cursor_y < marker_y):
            start = (cursor.x, cursor_y)
            end = (marker_x, marker_y)

        self._copy(start, end)
        self.toggle_mark()

    def copy_thing(self, thing):
        if thing == "selection":
            self._copy_selection()
            return

        self.fake_marker = False
        old_virtual_cursor_x, old_virtual_cursor_y, old_max_virtual_cursor_x = (
            self.virtual_cursor.x,
            self.virtual_cursor.y,
            self.max_virtual_cursor_x,
        )
        x = self.virtual_cursor.x - 1
        x = 0 if x < 0 else x

        after_pattern_match = bool(
            get_regexp(thing).match(self.get_line(self.virtual_cursor.y)[x].data)
        )
        if after_pattern_match:
            self.next_thing(thing)
        else:
            self.previous_thing(thing)

        if self.virtual_cursor.y == old_virtual_cursor_y - 1:
            self.virtual_cursor.x, self.virtual_cursor.y = 0, old_virtual_cursor_y

        self.toggle_mark()
        start = (self.virtual_cursor.x, self.virtual_cursor.y)

        if after_pattern_match:
            self.previous_thing(thing)
        else:
            self.next_thing(thing)

        end = self.virtual_cursor.x, self.virtual_cursor.y
        self.virtual_cursor.x = old_virtual_cursor_x
        self.old_cursor.x, self.old_cursor.y = (
            self.virtual_cursor.x,
            self.virtual_cursor.y,
        )
        self.old_marker_cursor.x, self.old_marker_cursor.y = end
        self.max_virtual_cursor_x = old_max_virtual_cursor_x
        self.fake_marker = True

        self._copy(start, end)

    def copy_word(self):
        self.copy_thing("word")

    def copy_symbol(self):
        self.copy_thing("symbol")
