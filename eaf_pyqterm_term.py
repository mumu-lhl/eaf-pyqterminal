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


class BellThread(QThread):
    def __init__(self):
        QThread.__init__(self)

        self.bell_sound_path = get_emacs_vars(("eaf-pyqterminal-bell-sound-path",))[0]

    def run(self):
        playsound(self.bell_sound_path)


class QTerminalStream(ByteStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class QTerminalScreen(HistoryScreen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def write_process_input(self, data: str) -> None:
        self.send(data)

    def bell(self):
        thread = BellThread()
        bell_sound_threads.append(thread)
        thread.start()
