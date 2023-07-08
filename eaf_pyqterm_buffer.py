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

from core.buffer import Buffer

sys.path.append(os.path.dirname(__file__))

import eaf_pyqterm_widget as widget


class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        super().__init__(buffer_id, url, arguments, False)

        arguments_dict = json.loads(arguments)
        backend = widget.backend
        backend.argv = shlex.split(arguments_dict["command"])
        backend.start_directory = arguments_dict["directory"]

        term = widget.QTerminalWidget()
        term.buffer_id = buffer_id
        term.change_title = self.change_title
        term.backend.close_buffer = self.close_buffer
        self.resize_view = term.resize_view

        self.add_widget(term)
        self.build_all_methods(term)
