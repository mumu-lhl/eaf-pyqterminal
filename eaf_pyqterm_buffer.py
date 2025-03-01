# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import shlex
import sys

from core.utils import *
from core.buffer import Buffer

sys.path.append(os.path.dirname(__file__))

from eaf_pyqterm_frontend import FrontendWidget


class AppBuffer(Buffer):
    def __init__(self, buffer_id, url, arguments):
        super().__init__(buffer_id, url, arguments, False)

        arguments_dict = json.loads(arguments)
        argv = shlex.split(arguments_dict["command"])
        start_directory = arguments_dict["directory"]
        self.term = FrontendWidget(argv, start_directory)

        self.term.buffer_id = buffer_id
        self.term.change_title = self.change_title
        self.term.backend.close_buffer = self.close_buffer
        self.term.send_input_message = self.send_input_message

        self.resize_view = self.term.resize_view
        self.fetch_marker_callback = self.term.fetch_marker_callback
        self.handle_input_response = self.term.handle_input_response
        self.cancel_input_response = self.term.cancel_input_response

        self.add_widget(self.term)
        self.build_all_methods(self.term)

    @interactive
    def update_theme(self):
        super().update_theme()
        
        self.term.init_color_schema()
        self.term.resize_view()
        self.term.update()
