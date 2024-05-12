# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import threading
import time

import pyte_
from core.utils import *
from PyQt6.QtWidgets import QApplication
from pyte_.screens import Cursor, HistoryScreen
from pyte.streams import ByteStream
from eaf_pyqterm_utils import get_regexp


class TerminalStream(ByteStream):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class TerminalScreen(HistoryScreen):
    def __init__(self, is_buffer, columns, lines, history):
        super().__init__(columns, lines, history)

        self.is_buffer = is_buffer

        self.base = 0
        self.in_history = False

        self.auto_scroll_lock = True
        self.current_thread = None

        self.cursor_move_mode = False
        self.before_is_cursor_move_mode = False

        self.cursor_dirty = False

        self.marker = ()
        self.fake_marker = False
        self.first_move = False
        self.max_virtual_cursor_x = 0
        self.absolute_virtual_cursor_y = 0
        self.virtual_cursor = Cursor(0, 0, self.default_char)
        self.old_cursor = Cursor(0, 0, self.default_char)
        self.old_marker_cursor = Cursor(0, 0, self.default_char)

        self.mouse = False

    def absolute_y(self, line_num: int) -> int:
        return self.base + line_num

    def at_top(self) -> bool:
        return self.base == 0 and self.virtual_cursor.y == 0

    def at_bottom(self) -> bool:
        return (
            not self.in_history
            and self.virtual_cursor.y + 1 == self.get_last_blank_line()
        )

    def bell(self) -> None:
        QApplication.beep()

    def sync_cursor(self) -> None:
        self.old_cursor.x = self.virtual_cursor.x
        self.old_cursor.y = self.virtual_cursor.y

    def scroll_up(self, line_num: int) -> None:
        if self.is_buffer:
            return

        base = self.base
        old_base = base

        if base != 0:
            self.in_history = True

        base = base - line_num
        if base < 0:
            base = 0
        self.base = base

        if base != old_base:
            self.dirty.update(range(self.lines))

    def scroll_down(self, line_num: int) -> None:
        if self.is_buffer:
            return

        base = self.base
        old_base = base

        base = base + line_num

        history = self.history
        if base >= len(history.top):
            base = len(history.top)
            self.in_history = False

        self.base = base

        if base != old_base:
            self.dirty.update(range(self.lines))

    def scroll_to_begin(self) -> None:
        if self.is_buffer:
            return

        self.scroll_up(self.base)

        if self.cursor_move_mode:
            self.virtual_cursor.x, self.virtual_cursor.y = 0, 0

    def scroll_to_bottom(self) -> None:
        if self.is_buffer:
            return

        if self.in_history:
            self.base = len(self.history.top)
            self.in_history = False
            self.dirty.update(range(self.lines))

        if self.cursor_move_mode:
            self.virtual_cursor.x, self.virtual_cursor.y = (
                self.columns - 1,
                self.get_last_blank_line() - 1,
            )
            self.adjust_x(self.virtual_cursor.y)

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

    def get_cursor(self) -> pyte_.screens.Cursor:
        if self.cursor_move_mode:
            if not self.mouse:
                return self.virtual_cursor
            elif self.in_history:
                self.cursor.hidden = True
        return self.cursor

    def get_line_display(
        self,
        line_num: int,
        *,
        in_buffer: bool = False,
        start: int = 0,
        end: int | None = None,
        absolute: bool = False,
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

    def get_end_x(self, line_num: int) -> int:
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

    def get_marker_y(self) -> int:
        return marker_y

    def toggle_cursor_move_mode(self, status: None | bool) -> None:
        if status is None:
            status = not self.cursor_move_mode

        if status:
            self.cursor_dirty = True

            if self.marker:
                self.toggle_mark()
        else:
            if self.in_history:
                self.scroll_to_bottom()
                self.in_history = False

            if self.marker:
                self.toggle_mark()
                self.toggle_mark()

        self.cursor_move_mode = status
        self.virtual_cursor.x, self.virtual_cursor.y = self.cursor.x, self.cursor.y
        self.virtual_cursor.hidden = False
        self.first_move = True
        self.fake_marker = False
        self.mouse = False

        eval_in_emacs("eaf--toggle-cursor-move-mode", ["'t" if status else "'nil"])

    def adjust_x(self, y: int) -> None:
        """Recalibrate the x of the virtual cursor."""

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

        self.adjust_x(self.virtual_cursor.y)

    def previous_line(self) -> None:
        y = self.virtual_cursor.y - 1

        if y < 0:
            self.scroll_up(1)
        else:
            self.virtual_cursor.y = y
            self.dirty.add(y)

        self.adjust_x(self.virtual_cursor.y)

    def next_character(self, num: int = 1) -> None:
        x = self.virtual_cursor.x + num
        end_x = self.get_end_x(self.virtual_cursor.y)
        line = self.get_line(self.virtual_cursor.y)

        # Skip two width character
        if line[x].data == "":
            x += 1

        if x > end_x and not self.at_bottom():
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

        if line[x].data == "":
            x -= 1

        if x < 0 and not self.at_top():
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

        if x is None and self.at_bottom():
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

        if x is None and self.at_top():
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
        if self.marker:
            old_marker_y = self.marker[1] - self.base
            if old_marker_y < 0:
                old_marker_y = 0
            elif old_marker_y >= self.lines:
                old_marker_y = self.lines - 1
        else:
            old_marker_y = cursor.y

        if self.marker == (cursor.x, self.absolute_y(cursor.y)) or self.fake_marker:
            self.marker = ()
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
            elif not self.mouse:
                cursor = self.old_marker_cursor

        marker_x, marker_y = self.marker[0], self.marker[1] - self.base
        end_x = self.get_end_x(y)

        if marker_y < 0:
            marker_x = 0
        elif marker_y >= self.lines:
            marker_x = self.get_end_x(self.lines - 1)

        if self.mouse:
            cursor.y = self.absolute_virtual_cursor_y - self.base

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
        cursor = self.virtual_cursor
        old_virtual_cursor_x = cursor.x
        old_virtual_cursor_y = cursor.y
        old_max_virtual_cursor_x = self.max_virtual_cursor_x
        x = cursor.x - 1
        x = 0 if x < 0 else x

        line = self.get_line(cursor.y)
        regexp = get_regexp(thing)
        after_match = bool(regexp.match(line[x].data))
        current_match = bool(regexp.match(line[cursor.x].data))

        if after_match and current_match:
            message_to_emacs("Nothing selected")
            return

        if not after_match:
            self.previous_thing(thing)

        if cursor.y == old_virtual_cursor_y - 1:
            cursor.x, cursor.y = 0, old_virtual_cursor_y

        self.toggle_mark()
        start = (cursor.x, cursor.y + self.base)

        self.next_thing(thing)
        end = (cursor.x, cursor.y + self.base)

        cursor.x = old_virtual_cursor_x
        self.sync_cursor()
        self.old_marker_cursor.x = end[0]
        self.old_marker_cursor.y = end[1] - self.base
        self.max_virtual_cursor_x = old_max_virtual_cursor_x
        self.fake_marker = True

        self._copy(start, end)

    def move_to_position(self, x: int, y: int) -> None:
        last_blank_line = self.get_last_blank_line()
        if not self.in_history and y >= last_blank_line:
            return

        if y >= self.lines:
            y = self.lines - 1
        elif y < 0:
            x, y = 0, 0

        self.update_line(y, self.virtual_cursor.y)
        self.virtual_cursor.x, self.virtual_cursor.y = x, y
        self.max_virtual_cursor_x = x
        self.adjust_x(y)

    def set_marker(self, x, y):
        end_x = self.get_end_x(y)
        last_blank_line = self.get_last_blank_line()

        x = x if x <= end_x else end_x
        y = y if y < last_blank_line else last_blank_line

        self.marker = (x, y + self.base)

    def _auto_scroll_up(self) -> None:
        while not self.auto_scroll_lock:
            self.scroll_up(1)
            self.absolute_virtual_cursor_y -= 1

            # Need to recalibrate the x of the virtual cursor to avoid
            # the virtual cursor being displayed at the empty end of a line
            self.adjust_x(self.virtual_cursor.y)

            time.sleep(0.05)

    def _auto_scroll_down(self) -> None:
        while not self.auto_scroll_lock:
            self.scroll_down(1)
            self.absolute_virtual_cursor_y += 1
            self.adjust_x(self.virtual_cursor.y)
            time.sleep(0.05)

    def auto_scroll_up(self) -> None:
        self.auto_scroll_lock = False
        self.current_thread = threading.Thread(target=self._auto_scroll_up)
        self.current_thread.start()

    def auto_scroll_down(self) -> None:
        self.auto_scroll_lock = False
        self.current_thread = threading.Thread(target=self._auto_scroll_down)
        self.current_thread.start()

    def disable_auto_scroll(self) -> None:
        self.auto_scroll_lock = True
        self.current_thread.join()
        self.current_thread = None
