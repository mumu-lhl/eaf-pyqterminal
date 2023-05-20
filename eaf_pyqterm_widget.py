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
import sys

import pyte
from core.utils import get_emacs_vars
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QWidget

sys.path.append(os.path.dirname(__file__))

import eaf_pyqterm_backend as backend

CSI_C0 = pyte.control.CSI_C0
KEY_DICT = {
    Qt.Key.Key_AsciiTilde: chr(126),
    Qt.Key.Key_Backspace: pyte.control.DEL,
    Qt.Key.Key_Delete: pyte.control.DEL,
    Qt.Key.Key_Down: CSI_C0 + "B",
    Qt.Key.Key_End: CSI_C0 + "F",
    Qt.Key.Key_Escape: pyte.control.ESC,
    Qt.Key.Key_Home: CSI_C0 + "H",
    Qt.Key.Key_Left: CSI_C0 + "D",
    Qt.Key.Key_Return: "\r",
    Qt.Key.Key_Right: CSI_C0 + "C",
    Qt.Key.Key_Tab: "\t",
    Qt.Key.Key_Up: CSI_C0 + "A",
}

align = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft


class QTerminalWidget(QWidget):
    pens = {}
    brushes = {}
    fonts = {}

    title = ""

    def __init__(self):
        super().__init__()

        self.init_vars()

        self.startTimer(self.refresh_ms)

        font = self.new_font()
        self.font = font

        self.fm = QFontMetrics(font)
        self._char_height = self.fm.height()
        self._char_width = self.get_text_width("W")
        self._columns, self._rows = self.pixel2pos(self.width(), self.height())

        self.cursor_x = 0
        self.cursor_y = 0
        self._selection = None

        self.default_brush = QBrush(self.colors["background"])
        self.default_pen = QPen(self.colors["foreground"])

        self.backend = backend.PtyBackend(self._columns, self._rows)
        self.pixmap = QPixmap(self.width(), self.height())

    def init_vars(self):
        (
            self.font_size,
            self.font_family,
            color_schema,
            self.refresh_ms,
            self.cursor_type,
            self.cursor_size,
        ) = get_emacs_vars(
            (
                "eaf-pyqterminal-font-size",
                "eaf-pyqterminal-font-family",
                "eaf-pyqterminal-color-schema",
                "eaf-pyqterminal-refresh-ms",
                "eaf-pyqterminal-cursor-type",
                "eaf-pyqterminal-cursor-size",
            )
        )

        self.colors = {}
        for name, color_str in color_schema:
            color = QColor(color_str)
            if name == "cursor":
                self.cursor_color = color
                continue
            self.colors[name] = color

    def new_font(self, style=[]):
        font = QFont()
        font.setFamily(self.font_family)
        font.setPixelSize(self.font_size)
        for s in style:
            if s == "bold":
                font.setBold(True)
            if s == "underscore":
                font.setUnderline(True)
            if s == "italics":
                font.setItalic(True)
            if s == "strikethrough":
                font.setStrikeOut(True)
        return font

    def get_font(self, style: list[str] = []) -> QFont:
        id = str(style)
        if id in self.fonts:
            return self.fonts[id]

        font = self.new_font(style)
        self.fonts[id] = font
        return font

    def get_color(self, color_name: str) -> QColor | str:
        if color_name in self.colors:
            return self.colors[color_name]
        if color_name == "default":
            return "default"

        color = QColor("#" + color_name)
        self.colors[color_name] = color
        return color

    def get_pen(self, color_name: str) -> QPen:
        pen = self.pens.get(color_name)
        if pen:
            return pen

        color = self.get_color(color_name)
        if color == "default":
            return self.default_pen

        pen = QPen(color)
        self.pens[color_name] = pen
        return pen

    def get_brush(self, color_name: str) -> QBrush:
        brush = self.brushes.get(color_name)
        if brush:
            return brush

        color = self.get_color(color_name)
        if color == "default":
            return self.default_brush

        brush = QBrush(color)
        self.brushes[color_name] = brush
        return brush

    def pixel2pos(self, x, y):
        col = x // self._char_width
        row = y // self._char_height
        return col, row

    def resizeEvent(self, event):
        width = self.width()
        height = self.height()
        self._columns, self._rows = self.pixel2pos(width, height)
        self.backend.resize(self._columns, self._rows)
        self.pixmap = QPixmap(width, height)
        self.paint_full_pixmap()

    def timerEvent(self, event):
        cursor = self.backend.cursor()
        if (
            not self.backend.screen.dirty
            and self.cursor_x == cursor.x
            and self.cursor_y == cursor.y
        ):
            return

        self.paint_part_pixmap()
        self.update()

        title = self.backend.get_title()
        if self.title != title:
            self.title = title
            update_title(title)  # noqa: F821

    def paint_selection(self, painter):
        pass

    def draw_text(
        self,
        text: str,
        start_x: int,
        start_y: int,
        text_width: int,
        fg: str,
        bg: str,
        painter: QPainter,
        align: Qt.AlignmentFlag,
        style: list[str],
    ):
        rect = QRect(start_x, start_y, text_width, self._char_height)

        if bg != "default":
            painter.fillRect(rect, self.get_brush(bg))

        painter.setFont(self.get_font(style))
        painter.setPen(self.get_pen(fg))
        painter.drawText(rect, align, text)

    def paint_full_text(self, painter: QPainter):
        for line_num in range(self._rows):
            self.paint_line_text(painter, line_num)

    def paint_dirty_text(self, painter: QPainter):
        screen = self.backend.screen

        # redraw the old cursor line
        screen.dirty.add(self.cursor_y)

        # dirty will change when traversing
        for _ in range(len(screen.dirty)):
            line_num = screen.dirty.pop()
            self.paint_line_text(painter, line_num)

    def paint_line_text(self, painter: QPainter, line_num: int):
        start_x = 0
        start_y = line_num * self._char_height
        screen = self.backend.screen

        clear_rect = QRect(start_x, start_y, self.width(), self._char_height)
        painter.fillRect(clear_rect, self.default_brush)

        line = screen.buffer[line_num]

        pre_char = None
        same_text = ""
        text_width = 0

        for col in range(screen.columns + 1):
            char = line[col]
            if col == screen.columns:
                char = None

            if (
                char
                and pre_char
                and pre_char.bg == char.bg
                and pre_char.fg == char.fg
                and pre_char.reverse == char.reverse
                and pre_char.bold == char.bold
                and pre_char.italics == char.italics
                and pre_char.underscore == char.underscore
                and pre_char.strikethrough == char.strikethrough
            ):
                same_text += char.data
                continue
            elif same_text:
                text_width = self.get_text_width(same_text)

                fg = "white" if pre_char.fg == "default" else pre_char.fg
                bg = "black" if pre_char.bg == "default" else pre_char.bg
                if pre_char.reverse:
                    fg, bg = bg, fg

                style = []
                if pre_char.bold:
                    style.append("bold")
                if pre_char.italics:
                    style.append("italics")
                if pre_char.underscore:
                    style.append("underscore")
                if pre_char.strikethrough:
                    style.append("strikethrough")

                self.draw_text(
                    same_text,
                    start_x,
                    start_y,
                    text_width,
                    fg,
                    bg,
                    painter,
                    align,
                    style,
                )

            if char:
                pre_char = char
                same_text = char.data
                start_x = start_x + text_width

    def paint_cursor(self, painter: QPainter):
        cursor = self.backend.cursor()

        if cursor.hidden:
            return

        self.cursor_x = cursor.x
        self.cursor_y = cursor.y

        screen = self.backend.screen
        line = screen.buffer[cursor.y]
        before_text = "".join(
            [line[char_number].data for char_number in range(cursor.x)]
        )

        cursor_width = self._char_width
        cursor_height = self._char_height
        cursor_x = self.get_text_width(before_text)
        cursor_y = self.cursor_y * self._char_height
        if self.cursor_type == "bar":
            cursor_height = self.cursor_size
            cursor_y += self._char_height - cursor_height
        elif self.cursor_type == "hbar":
            cursor_width = self.cursor_size

        bcol = QColor(self.cursor_color)
        bcol.setAlpha(80)
        brush = QBrush(bcol)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRect(QRect(cursor_x, cursor_y, cursor_width, cursor_height))

    def paint_full_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_full_text(painter)
        self.paint_cursor(painter)

    def paint_part_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_dirty_text(painter)
        self.paint_cursor(painter)

    def get_text_width(self, text: str):
        return self.fm.horizontalAdvance(text)

    def focusProxy(self):
        return self

    def send(self, data):
        self.backend.send(data)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

    def keyPressEvent(self, event: QKeyEvent):
        text = str(event.text())
        key = event.key()
        modifier = event.modifiers()
        s = KEY_DICT.get(key)

        if (text or s) and modifier == Qt.KeyboardModifier.ControlModifier:
            # 'a' => '\x01', 'A' => '\x01'
            text = chr(ord(text.lower()) - 96)
            self.send(text)
            return
        if (text or s) and modifier == Qt.KeyboardModifier.AltModifier:
            text = s if s else text
            self.send(pyte.control.ESC + text)
            return

        if text and not s:
            self.send(text)
            return

        if s:
            event.accept()
            self.send(s)

    def closeEvent(self, event):
        self.backend.close()

    def wheelEvent(self, event: QWheelEvent):
        y = event.angleDelta().y()
        if y > 0:
            self.backend.screen.prev_page()
        else:
            self.backend.screen.next_page()
            self.update()
