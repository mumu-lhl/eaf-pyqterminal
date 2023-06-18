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


from core.utils import get_emacs_vars
from playsound import playsound
from pyte.screens import HistoryScreen
from pyte.streams import ByteStream

bell_sound_path = get_emacs_vars(("eaf-pyqterminal-bell-sound-path",))[0]


class QTerminalStream(ByteStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class QTerminalScreen(HistoryScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.base = 0
        self.in_history = False

    def bell(self):
        playsound(bell_sound_path, False)

    def exit_history(self):
        if self.in_history:
            self.base = len(self.history.top)
            self.in_history = False
            self.dirty.update(range(self.lines))

    def scroll_up(self, line_num):
        if self.base != 0:
            self.in_history = True

        base = self.base - line_num
        self.base = 0 if base < 0 else base

        self.dirty.update(range(self.lines))

    def scroll_down(self, line_num):
        base = self.base + line_num

        if base >= len(self.history.top):
            base = len(self.history.top)
            self.in_history = False

        self.base = base

        self.dirty.update(range(self.lines))

    def get_line(self, line_num):
        if not self.in_history:
            self.base = len(self.history.top)

        history_line_num = self.base + line_num

        if history_line_num <= len(self.history.top) - 1:
            return self.history.top[history_line_num]
        else:
            return self.buffer[self.base - len(self.history.top) + line_num]

    # https://github.com/selectel/pyte/blob/a1c089e45b5d0eef0f3450984350254248f02519/pyte/screens.py#L286
    def resize(self, lines=None, columns=None):
        lines = lines or self.lines
        columns = columns or self.columns

        if lines == self.lines and columns == self.columns:
            return  # No changes.

        self.dirty.update(range(lines))

        count = self.lines - lines
        if count > 0 and self.cursor.y >= lines:
            self.cursor.y -= count

            for y in range(self.lines):
                if y < count:
                    self.history.top.append(self.buffer.pop(y))
                else:
                    self.buffer[y - count] = self.buffer.pop(y)
        elif count < 0:
            top_length = len(self.history.top)
            count = -count
            count = top_length if top_length < count else count

            for y in range(self.lines + count - 1, -1, -1):
                index = y - count
                if index >= 0:
                    self.buffer[y] = self.buffer[index]
                else:
                    self.buffer[y] = self.history.top[index]

        if columns < self.columns:
            for line in self.buffer.values():
                for x in range(columns, self.columns):
                    line.pop(x, None)

        self.lines, self.columns = lines, columns
