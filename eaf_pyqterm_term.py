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

import pyte
from core.utils import *
from playsound import playsound
from pyte.screens import Cursor, HistoryScreen
from pyte.streams import ByteStream

BELL_SOUND_PATH = get_emacs_vars(("eaf-pyqterminal-bell-sound-path",))[0]


def get_regexp(thing: str):
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
        self.before_is_cursor_move_mode = False
        self.cursor_dirty = False
        self.fake_marker = False
        self.mouse = False
        self.first_move = True
        self.virtual_cursor = Cursor(0, 0)
        self.old_cursor = Cursor(0, 0)
        self.old_marker_cursor = Cursor(0, 0)
        self.max_virtual_cursor_x = 0
        self.marker = ()
        self.last_update_line = ()

    def absolute_y(self, line_num: int) -> int:
        return self.base + line_num

    @property
    def at_top(self) -> int:
        return self.base == 0 and self.virtual_cursor.y == 0

    @property
    def at_bottom(self) -> int:
        return (
            not self.in_history
            and self.virtual_cursor.y + 1 == self.get_last_blank_line()
        )

    def bell(self) -> None:
        playsound(BELL_SOUND_PATH, False)

    def scroll_up(self, line_num: int) -> None:
        if self.is_buffer:
            return

        if self.base != 0:
            self.in_history = True

        base = self.base - line_num
        old_base = self.base
        self.base = 0 if base < 0 else base

        if self.base != old_base:
            self.dirty.update(range(self.lines))

    def scroll_down(self, line_num: int) -> None:
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

    def scroll_to_begin(self) -> None:
        if self.is_buffer:
            return

        self.scroll_up(self.base)
        self.virtual_cursor.x, self.virtual_cursor.y = 0, 0

    def scroll_to_bottom(self) -> None:
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

    def get_line(self, line_num: int, absolute: bool = False):
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
            return self.buffer[history_line_num - top_length]

    def get_cursor(self) -> pyte.screens.Cursor:
        return self.virtual_cursor if self.cursor_move_mode else self.cursor

    def get_line_display(
        self,
        line_num: int,
        *,
        in_buffer: bool = False,
        start: int = 0,
        end: int | None = None,
        absolute: bool = False
    ) -> str:
        if end is None:
            end = self.columns

        line = self.buffer[line_num] if in_buffer else self.get_line(line_num, absolute)
        return "".join(line[x].data for x in range(start, end))

    def get_last_blank_line(self) -> int:
        for y in range(self.lines - 1, -1, -1):
            if self.get_line_display(y, in_buffer=True).strip() != "":
                return y + 1

        return 0

    def get_end_x(self, line_num) -> int:
        line = self.get_line(line_num)
        for x in range(self.columns - 1, -1, -1):
            if line[x].data != " ":
                return x + 1

        return 0

    def resize(self, lines: int | None = None, columns: int | None = None) -> None:
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

    def toggle_cursor_move_mode(self, status: None | bool) -> None:
        if status is None:
            status = not self.cursor_move_mode

        if not status and self.in_history:
            self.base = len(self.history.top)
            self.in_history = False
            self.dirty.update(range(self.lines))
        elif status:
            self.cursor_dirty = True

        self.cursor_move_mode = status
        self.virtual_cursor.x, self.virtual_cursor.y = self.cursor.x, self.cursor.y
        self.virtual_cursor.hidden = False
        self.first_move = True
        self.fake_marker = False

        eval_in_emacs("eaf--toggle-cursor-move-mode", ["'t" if status else "'nil"])

        if self.marker != ():
            self.marker = ()
            self.dirty.update(range(self.lines))

    def jump_x(self, y: int) -> None:
        if self.first_move:
            self.first_move = False
            self.max_virtual_cursor_x = self.virtual_cursor.x

        self.virtual_cursor.x = self.max_virtual_cursor_x

        if self.get_line(self.virtual_cursor.y)[self.virtual_cursor.x].data == " ":
            max_x = self.get_end_x(y)
            if max_x < self.virtual_cursor.x:
                self.virtual_cursor.x = max_x

    def next_line(self) -> None:
        y = self.virtual_cursor.y + 1

        if not self.in_history and y == self.get_last_blank_line():
            return

        if y > self.lines - 1:
            self.scroll_down(1)
        else:
            self.virtual_cursor.y = y
            self.dirty.add(y)

        self.jump_x(self.virtual_cursor.y)

    def previous_line(self) -> None:
        y = self.virtual_cursor.y - 1

        if y < 0:
            self.scroll_up(1)
        else:
            self.virtual_cursor.y = y
            self.dirty.add(y)

        self.jump_x(self.virtual_cursor.y)

    def next_character(self, num: int = 1) -> None:
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

    def previous_character(self, num: int = 1) -> None:
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

    def find(
        self, y: int, pattern: re.Pattern, start: int, reverse: bool = False
    ) -> int | None:
        line = self.get_line(y)
        iterator = (
            range(start - 1, -2, -1) if reverse else range(start, self.get_end_x(y) + 1)
        )
        string_match = False

        for column in iterator:
            pattern_match = bool(pattern.match(line[column].data))

            if string_match and pattern_match:
                return column

            if not pattern_match:
                string_match = True

        return None

    def next_thing(self, thing: str, first: bool = True) -> None:
        start = self.virtual_cursor.x if first else 0
        x = self.find(self.virtual_cursor.y, get_regexp(thing), start)

        self.move_beginning_of_line()

        if x is None and self.at_bottom:
            self.move_end_of_line()
            return

        if x is None:
            self.next_line()
            self.next_thing(thing, False)
        else:
            self.next_character(x)

    def previous_thing(self, thing: str, first: bool = True) -> None:
        start = (
            self.virtual_cursor.x if first else self.get_end_x(self.virtual_cursor.y)
        )
        x = self.find(self.virtual_cursor.y, get_regexp(thing), start, True)

        if x is None and self.at_top:
            self.move_beginning_of_line()
            return

        if x is None:
            self.previous_line()
            self.move_end_of_line()
            self.previous_thing(thing, False)
        else:
            self.move_beginning_of_line()
            self.next_character(x + 1)

    def move_beginning_of_line(self) -> None:
        self.virtual_cursor.x = 0
        self.max_virtual_cursor_x = 0

    def move_end_of_line(self) -> None:
        self.virtual_cursor.x = self.get_end_x(self.virtual_cursor.y)
        self.max_virtual_cursor_x = self.virtual_cursor.x

    def update_line(self, y1: int, y2: int) -> None:
        if y1 == y2:
            self.dirty.add(y1)
        else:
            start = min(y1, y2)
            end = max(y1, y2)
            self.dirty.update(range(start, end + 1))

    def toggle_mark(self) -> None:
        cursor = self.virtual_cursor
        if self.marker != ():
            (_, old_marker_y) = self.marker
            old_marker_y -= self.base
        else:
            old_marker_y = cursor.y

        if (
            self.marker == (cursor.x, self.absolute_y(cursor.y))
            or self.fake_marker
            and not self.mouse
        ):
            self.marker = ()
            self.cursor_dirty = True
        else:
            self.marker = (cursor.x, self.absolute_y(cursor.y))

            self.update_line(cursor.y, old_marker_y)

    def get_selection(self, y: int) -> range:
        if self.marker == ():
            return range(0)

        cursor = self.virtual_cursor

        if self.fake_marker:
            if cursor.x != self.old_cursor.x or cursor.y != self.old_cursor.y:
                self.toggle_mark()
                self.fake_marker = False
                return range(0)
            else:
                cursor = self.old_marker_cursor

        (marker_x, marker_y) = self.marker
        marker_y -= self.base
        end_x = self.get_end_x(y)

        if cursor.y < y < marker_y or cursor.y > y > marker_y:
            return range(0, end_x)
        elif cursor.y == y == marker_y:
            return range(min(cursor.x, marker_x), max(cursor.x, marker_x))
        elif y == cursor.y:
            if marker_y < cursor.y:
                return range(0, cursor.x)
            else:
                return range(cursor.x, end_x)
        elif y == marker_y:
            if marker_y < cursor.y:
                return range(marker_x, end_x)
            else:
                return range(0, marker_x)

        return range(0)

    def _copy(self, start: int, end: int) -> None:
        text = ""

        for y in range(start[1], end[1] + 1):
            start_x = start[0] if y == start[1] else 0
            end_x = end[0] if y == end[1] else self.columns
            line = self.get_line_display(
                y, in_buffer=self.is_buffer, start=start_x, end=end_x, absolute=True
            )
            line_strip = line.rstrip()
            text += line if line == line_strip else line_strip + "\n"

        message_to_emacs("Copy text")
        set_clipboard_text(text)

    def _copy_selection(self) -> None:
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
        self.toggle_mark()

        if self.mouse:
            self.mouse = False

            if not self.before_is_cursor_move_mode:
                if self.in_history:
                    self.cursor_move_mode = False
                    self.virtual_cursor.hidden = True
                    eval_in_emacs("eaf--toggle-cursor-move-mode", ["'nil"])
                else:
                    self.toggle_cursor_move_mode(False)

    def copy_thing(self, thing: str) -> None:
        if thing == "selection":
            self._copy_selection()
            return

        self.marker = ()
        self.fake_marker = False
        old_virtual_cursor_x, old_virtual_cursor_y = (
            self.virtual_cursor.x,
            self.virtual_cursor.y,
        )
        old_max_virtual_cursor_x = self.max_virtual_cursor_x
        x = self.virtual_cursor.x - 1
        x = 0 if x < 0 else x

        after_match = bool(
            get_regexp(thing).match(
                self.get_line(self.virtual_cursor.y)[self.virtual_cursor.x - 1].data
            )
        )
        current_match = bool(
            get_regexp(thing).match(
                self.get_line(self.virtual_cursor.y)[self.virtual_cursor.x].data
            )
        )

        if after_match and current_match:
            message_to_emacs("Nothing selected")
            return

        if not after_match:
            self.previous_thing(thing)

        if self.virtual_cursor.y == old_virtual_cursor_y - 1:
            self.virtual_cursor.x, self.virtual_cursor.y = 0, old_virtual_cursor_y

        self.toggle_mark()
        start = (self.virtual_cursor.x, self.virtual_cursor.y + self.base)

        self.next_thing(thing)

        end = (self.virtual_cursor.x, self.virtual_cursor.y + self.base)
        self.virtual_cursor.x = old_virtual_cursor_x
        self.old_cursor.x, self.old_cursor.y = (
            self.virtual_cursor.x,
            self.virtual_cursor.y,
        )
        self.old_marker_cursor.x, self.old_marker_cursor.y = end
        self.max_virtual_cursor_x = old_max_virtual_cursor_x
        self.fake_marker = True

        self._copy(start, end)

    def move_to_position(self, x: int, y: int) -> None:
        last_blank_line = self.get_last_blank_line()
        if not self.in_history and y >= last_blank_line:
            return
        self.update_line(y, self.virtual_cursor.y)
        self.virtual_cursor.x, self.virtual_cursor.y = x, y
        self.max_virtual_cursor_x = x
        self.jump_x(y)
