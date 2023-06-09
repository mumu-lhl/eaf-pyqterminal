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
from core.buffer import interactive
from core.utils import *
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
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
    Qt.Key.Key_AsciiTilde: "~",
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

align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft


class QTerminalWidget(QWidget):
    brushes = {}
    colors = {}
    fonts = {}
    pens = {}

    def __init__(self):
        super().__init__()

        (
            self.font_size,
            self.font_family,
            color_schema,
            self.refresh_ms,
            self.cursor_type,
            self.cursor_size,
            self.cursor_alpha,
        ) = get_emacs_vars(
            (
                "eaf-pyqterminal-font-size",
                "eaf-pyqterminal-font-family",
                "eaf-pyqterminal-color-schema",
                "eaf-pyqterminal-refresh-ms",
                "eaf-pyqterminal-cursor-type",
                "eaf-pyqterminal-cursor-size",
                "eaf-pyqterminal-cursor-alpha",
            )
        )

        self.ensure_font_exist()

        for name, color_str in color_schema:
            color = QColor(color_str)
            if name == "cursor":
                self.cursor_color = color
                continue
            self.colors[name] = color

        self.theme_mode = get_emacs_theme_mode()
        theme_foreground_color = get_emacs_theme_foreground()
        theme_background_color = get_emacs_theme_background()

        self.colors["foreground"] = QColor(theme_foreground_color)
        self.colors["background"] = QColor(theme_background_color)
        self.colors["black"] = (
            QColor(theme_background_color)
            if self.theme_mode == "dark"
            else QColor("#000000")
        )
        self.colors["white"] = (
            QColor(theme_background_color)
            if self.theme_mode == "light"
            else QColor("#FFFFFF")
        )

        self.pens["default"] = QPen(self.colors["foreground"])
        self.brushes["default"] = QBrush(self.colors["background"])

        self.title = ""

        self.cursor_x = 0
        self.cursor_y = 0

        self.selection = None

        self.font = self.new_font()

        self.fm = QFontMetricsF(self.font)
        self.char_height = self.fm.height()
        self.char_width = self.fm.maxWidth()
        self.columns, self.rows = self.pixel2pos(self.width(), self.height())
        print(self.fm.horizontalAdvance("W" * 8))

        self.backend = backend.PtyBackend(self.columns, self.rows)
        self.pixmap = QPixmap(self.width(), self.height())

        self.startTimer(self.refresh_ms)

    def ensure_font_exist(self):
        """Use system Mono font if user's font is not exist."""
        if self.font_family not in QFontDatabase.families():
            self.font_family = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            ).family()

    def new_font(self, style=[]):
        font = QFont()
        font.setFamily(self.font_family)
        font.setPixelSize(self.font_size)

        if "bold" in style:
            font.setBold(True)
        if "underscore" in style:
            font.setUnderline(True)
        if "italics" in style:
            font.setItalic(True)
        if "strikethrough" in style:
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
        pen = QPen(color)
        self.pens[color_name] = pen
        return pen

    def get_brush(self, color_name: str) -> QBrush:
        brush = self.brushes.get(color_name)
        if brush:
            return brush

        color = self.get_color(color_name)
        brush = QBrush(color)
        self.brushes[color_name] = brush
        return brush

    def pixel2pos(self, x, y):
        col = int(x / self.char_width - 1)
        row = int(y / self.char_height)
        return col, row

    def resizeEvent(self, event):
        width = self.width()
        height = self.height()
        self.columns, self.rows = self.pixel2pos(width, height)
        self.backend.resize(self.columns, self.rows)
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
            self.change_title(f"Term [{title}]")

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
        style: list[str],
    ):
        if text.strip() == "" and bg == "default":
            return

        rect = QRectF(start_x, start_y, text_width, self.char_height)

        if bg != "default":
            painter.fillRect(rect, self.get_brush(bg))

        painter.setFont(self.get_font(style))
        painter.setPen(self.get_pen(fg))
        painter.drawText(rect, align, text)

    def paint_full_text(self, painter: QPainter):
        for line_num in range(self.rows):
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
        start_y = line_num * self.char_height
        screen = self.backend.screen

        clear_rect = QRectF(start_x, start_y, self.width(), self.char_height)
        painter.fillRect(clear_rect, self.get_brush("default"))

        line = screen.buffer[line_num]

        pre_char = pyte.screens.Char("")
        same_text = ""
        text_width = 0

        for col in range(screen.columns + 1):
            char = line[col]
            if col == screen.columns:
                char = None

            if (
                char
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
            elif same_text != "":
                text_width = self.get_text_width(same_text)

                if self.theme_mode == "dark":
                    fg = "white" if pre_char.fg == "default" else pre_char.fg
                    bg = "black" if pre_char.bg == "default" else pre_char.bg
                else:
                    fg = "black" if pre_char.fg == "default" else pre_char.fg
                    bg = "white" if pre_char.bg == "default" else pre_char.bg
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
                    style,
                )

            if char:
                pre_char = char
                same_text = char.data
                start_x += text_width

    def paint_cursor(self, painter: QPainter):
        cursor = self.backend.cursor()

        if cursor.hidden:
            return

        self.cursor_x = cursor.x
        self.cursor_y = cursor.y

        screen = self.backend.screen
        line = screen.buffer[cursor.y]
        before_text = ""
        for num in range(cursor.x):
            before_text += line[num].data
        text_width = self.get_text_width(before_text)

        cursor_width = self.char_width
        cursor_height = self.char_height
        cursor_x = text_width
        cursor_y = self.cursor_y * self.char_height
        if self.cursor_type == "bar":
            cursor_height = self.cursor_size
            cursor_y += self.char_height - cursor_height
        elif self.cursor_type == "hbar":
            cursor_width = self.cursor_size

        bcol = QColor(self.cursor_color)
        if self.cursor_alpha >= 0:
            bcol.setAlpha(self.cursor_alpha)
        brush = QBrush(bcol)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRect(QRectF(cursor_x, cursor_y, cursor_width, cursor_height))

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

    @interactive
    def yank_text(self):
        text = get_emacs_func_result("eaf-pyqterminal-get-clipboard", ())
        if isinstance(text, str):
            self.send(text)
