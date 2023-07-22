#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later

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
        term.send_input_message = self.send_input_message
        self.term = term
        self.resize_view = term.resize_view
        self.fetch_marker_callback = term.fetch_marker_callback
        self.handle_input_response = term.handle_input_response
        self.cancel_input_response = term.cancel_input_response

        self.add_widget(term)
        self.build_all_methods(term)
