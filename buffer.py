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

import json
import os
import shlex
import sys

from core.buffer import (
    Buffer,
    interactive,
)
from core.utils import get_emacs_func_result

sys.path.append(os.path.dirname(__file__))

import widget


class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        super().__init__(buffer_id, url, arguments, False)

        arguments_dict = json.loads(arguments)
        backend = widget.backend
        backend.argv = shlex.split(arguments_dict["command"])
        backend.start_directory = arguments_dict["directory"]

        backend.close_buffer = self.close_buffer
        widget.update_title = self.update_title

        self.term = widget.QTerminalWidget()
        self.add_widget(self.term)

    @interactive()
    def yank_text(self):
        text = get_emacs_func_result("eaf-pyqterminal-get-clipboard", ())
        if isinstance(text, str):
            self.term.send(text)

    @interactive
    def update_theme(self):
        super().update_theme()

    def update_title(self, title: str):
        self.change_title(f"Term [{title}]")
