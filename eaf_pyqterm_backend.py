# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import platform
import threading

import psutil

if platform.system() == "Windows":
    from winpty import PtyProcess as pty
else:
    import fcntl
    import pty
    import signal
    import struct
    import termios

from eaf_pyqterm_term import TerminalScreen, TerminalStream


class Pty:
    def __init__(self, width, height, argv, start_directory):
        env = os.environ
        env.update(
            {
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "COLUMNS": str(width),
                "LINES": str(height),
            }
        )

        if platform.system() == "Windows":
            self._spawn_winpty(env, argv, start_directory)
        else:
            self._spawn_pty(env, argv, start_directory)

    def _spawn_pty(self, env, argv, start_directory):
        p_pid, master_fd = pty.fork()
        if p_pid == 0:
            os.chdir(start_directory)
            os.execvpe(argv[0], argv, env)
        else:
            self.p_fd = master_fd
            self.p_pid = p_pid
            self.pty = os.fdopen(master_fd, "w+b", 0)

    def _spawn_winpty(self, env, argv, start_directory):
        self.pty = pty.spawn(
            argv,
            start_directory,
            env,
            (int(env["COLUMNS"]), int(env["LINES"])),
        )

    def read(self):
        return self.pty.read(65536)

    def write(self, data):
        if platform.system() == "Windows":
            self.pty.write(data.decode())
        else:
            self.pty.write(data)

    def close(self):
        self.pty.close()
        if platform.system() != "Windows":
            os.kill(self.p_pid, signal.SIGTERM)

    def resize(self, width, height):
        if platform.system() == "Windows":
            self._resize_winpty(width, height)
        else:
            self._resize_pty(width, height)

    def _resize_pty(self, width, height):
        # https://github.com/pexpect/ptyprocess/blob/ce42a786ff6f4baff71382db9076c7398328abaf/ptyprocess/ptyprocess.py#L118
        TIOCSWINSZ = getattr(termios, "TIOCSWINSZ", -2146929561)
        s = struct.pack("HHHH", height, width, 0, 0)
        try:
            fcntl.ioctl(self.p_fd, TIOCSWINSZ, s)
        except:  # noqa: E722
            pass

    def _resize_winpty(self, width, height):
        self.pty.setwinsize(cols=width, rows=height)

    def getcwd(self):
        pid = self.pty.pid if platform.system() == "Windows" else self.p_pid
        try:
            return psutil.Process(pid).cwd()
        except:  # noqa: E722
            pass


class Backend:
    def __init__(self, width, height, argv, start_directory):
        self.screen = TerminalScreen(False, width, height, 99999)
        self.buffer_screen = TerminalScreen(True, width, height, 99999)
        self.stream = TerminalStream(self.screen)
        self.buffer_stream = TerminalStream(self.buffer_screen)

        self.screen.write_process_input = self.send
        self.buffer_screen.write_process_input = self.send

        self.pty = Pty(width, height, argv, start_directory)
        self.getcwd = self.pty.getcwd

        self.thread = threading.Thread(target=self.read)
        self.thread.start()

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

        try:
            self.stream.feed(data)
        except:  # noqa: E722
            # Avoid problem with vim
            pass

    def into_buffer_screen(self):
        self.screen, self.buffer_screen = self.buffer_screen, self.screen
        self.stream, self.buffer_stream = self.buffer_stream, self.stream

    def exit_buffer_screen(self):
        self.screen, self.buffer_screen = self.buffer_screen, self.screen
        self.stream, self.buffer_stream = self.buffer_stream, self.stream
        self.buffer_screen.reset()
        self.screen.dirty.update(range(self.screen.lines))

    def read(self):
        if platform.system() == "Windows":
            while True:
                try:
                    data = self.pty.read().encode()
                    self.write_to_screen(data)
                except (OSError, IOError):
                    self.close()
                    break
        else:
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
        except:  # noqa: E722
            self.close()

    def close(self):
        self.pty.close()
        self.close_buffer()

