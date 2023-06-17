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
from PyQt6.QtCore import QThread
from pyte.screens import HistoryScreen
from pyte.streams import ByteStream

bell_sound_threads = []
bell_sound_path = get_emacs_vars(("eaf-pyqterminal-bell-sound-path",))[0]


class BellThread(QThread):
    def __init__(self):
        QThread.__init__(self)

    def run(self):
        playsound(bell_sound_path)


class QTerminalStream(ByteStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class QTerminalScreen(HistoryScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.base = 0
        self.in_history = False

    def write_process_input(self, data: str) -> None:
        self.send(data)

    def bell(self):
        thread = BellThread()
        bell_sound_threads.append(thread)
        thread.start()

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

        self.lines, self.columns = lines, columns
        self.set_margins()
