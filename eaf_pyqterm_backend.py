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

import os
import platform
import threading

import psutil

if platform == "Windows":
    from winpty import PtyProcess as pty
else:
    import fcntl
    import pty
    import signal
    import struct
    import termios

from eaf_pyqterm_term import QTerminalScreen, QTerminalStream


class Pty:
    def __init__(self, width, height):
        env = os.environ
        env.update(
            {
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "COLUMNS": str(width),
                "LINES": str(height),
            }
        )

        if platform == "Windows":
            self._spawn_winpty(env)
        else:
            self._spawn_pty(env)

    def _spawn_pty(self, env):
        p_pid, master_fd = pty.fork()
        if p_pid == 0:
            os.chdir(start_directory)  # noqa: F821
            os.execvpe(argv[0], argv, env)  # noqa: F821
        else:
            self.p_fd = master_fd
            self.p_pid = p_pid
            self.pty = os.fdopen(master_fd, "w+b", 0)

    def _spawn_winpty(self, env):
        self.pty = pty.spawn(
            list(argv[0]) + argv,  # noqa: F821
            start_directory,  # noqa: F821
            env,
            (env["COLUMNS"], env["LINES"]),
        )

    def read(self):
        return self.pty.read(65536)

    def write(self, data):
        self.pty.write(data)

    def close(self):
        self.pty.close()
        if platform != "Windows":
            os.kill(self.p_pid, signal.SIGTERM)

    def resize(self, width, height):
        if platform == "Windows":
            self._resize_winpty(width, height)
        else:
            self._resize_pty(width, height)

    def _resize_pty(self, width, height):
        # https://github.com/pexpect/ptyprocess/blob/ce42a786ff6f4baff71382db9076c7398328abaf/ptyprocess/ptyprocess.py#L118
        TIOCSWINSZ = getattr(termios, "TIOCSWINSZ", -2146929561)
        s = struct.pack("HHHH", height, width, 0, 0)
        try:
            fcntl.ioctl(self.p_fd, TIOCSWINSZ, s)
        except:
            pass

    def _resize_winpty(self, width, height):
        self.pty.set_size(width, height)

    def getcwd(self):
        pid = self.pty.pid if platform == "Windows" else self.p_pid
        try:
            return psutil.Process(pid).cwd()
        except:
            pass


class Backend:
    def __init__(self, width, height):
        self.screen = QTerminalScreen(False, width, height, 99999)
        self.buffer_screen = QTerminalScreen(True, width, height, 99999)
        self.stream = QTerminalStream(self.screen)
        self.buffer_stream = QTerminalStream(self.buffer_screen)

        self.screen.write_process_input = self.send
        self.buffer_screen.write_process_input = self.send

        self.pty = Pty(width, height)
        self.getcwd = self.pty.getcwd

        self.thread = threading.Thread(target=self.read)
        self.thread.start()

    @property
    def is_in_history(self):
        return bool(self.screen.history.bottom)

    @property
    def title(self):
        return self.screen.title or self.buffer_screen.title

    def resize(self, width, height):
        self.screen.resize(height, width)
        self.buffer_screen.resize(height, width)

        self.pty.resize(width, height)

    def write_to_screen(self, data: bytes):
        into = data.split(b"\x1b[?1049h")
        exit = data.split(b"\x1b[?1049l")

        if len(into) == 2:
            self.write_to_screen(into[0])
            self.into_buffer_screen()
            data = into[1]
        if len(exit) == 2:
            self.write_to_screen(exit[0])
            self.exit_buffer_screen()
            data = exit[1]

        self.stream.feed(data)

    def into_buffer_screen(self):
        self.screen, self.buffer_screen = self.buffer_screen, self.screen
        self.stream, self.buffer_stream = self.buffer_stream, self.stream

    def exit_buffer_screen(self):
        self.screen, self.buffer_screen = self.buffer_screen, self.screen
        self.stream, self.buffer_stream = self.buffer_stream, self.stream
        self.buffer_screen.reset()
        self.screen.dirty.update(range(self.screen.lines))

    def read(self):
        while True:
            try:
                data = self.pty.read()
                self.write_to_screen(data)
            except (OSError, IOError):
                self.close()
                break

    def send(self, data: str):
        try:
            self.pty.write(data.encode())
        except:
            self.close()

    def close(self):
        self.pty.close()
        self.close_buffer()
