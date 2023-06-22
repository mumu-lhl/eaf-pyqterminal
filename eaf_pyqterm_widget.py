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

import math
from enum import Enum

import pyte
from core.buffer import interactive
from core.utils import *
from PyQt6.QtCore import QLineF, QRectF, Qt
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

align = Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter

LineType = Enum("LineType", ("Underline", "StrikeOut"))
StyleType = Enum("StyleType", ("Bold", "Italics", "Underline", "StrikeOut"))


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

        self.directory = ""
        self.title = ""

        self.cursor_x = 0
        self.cursor_y = 0

        self.font = self.get_font()

        self.fm = QFontMetricsF(self.font)
        self.char_height = self.fm.height()
        self.char_width = self.get_text_width("W")
        self.columns, self.rows = self.pixel_to_position(self.width(), self.height())
        self.underline_pos = self.fm.underlinePos()

        self.backend = backend.Backend(self.columns, self.rows)
        self.pixmap = QPixmap(self.width(), self.height())

        self.startTimer(self.refresh_ms)

    def ensure_font_exist(self):
        """Use system Mono font if user's font is not exist."""
        if self.font_family not in QFontDatabase.families():
            self.font_family = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            ).family()

    def get_font(self, style: list[StyleType] = []) -> QFont:
        id = str(style)
        if id in self.fonts:
            return self.fonts[id]

        font = QFont()
        font.setFamily(self.font_family)
        font.setPixelSize(self.font_size)

        if StyleType.Bold in style:
            font.setBold(True)
        if StyleType.Italics in style:
            font.setItalic(True)

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

    def pixel_to_position(self, x, y):
        col = int(x / self.char_width)
        row = int(y / self.char_height)
        return col, row

    def resizeEvent(self, event):
        width = self.width()
        height = self.height()
        self.columns, self.rows = self.pixel_to_position(width, height)
        self.backend.resize(self.columns, self.rows)
        self.pixmap = QPixmap(width, height)
        self.paint_pixmap()

    def timerEvent(self, event):
        cursor = self.backend.cursor
        if (
            not self.backend.screen.dirty
            and self.cursor_x == cursor.x
            and self.cursor_y == cursor.y
        ):
            return

        self.paint_pixmap()
        self.update()

        title = self.backend.title
        if title != self.title:
            self.title = title
            self.change_title(f"Term [{title}]")

        directory = self.backend.getcwd()
        if directory and directory != self.directory:
            self.directory = directory
            eval_in_emacs("eaf--change-default-directory", [self.buffer_id, directory])

    def paint_text(self, painter: QPainter):
        screen = self.backend.screen

        # redraw the old cursor line
        screen.dirty.add(self.cursor_y)

        # dirty will change when traversing
        for _ in range(len(screen.dirty)):
            line_num = screen.dirty.pop()
            self.paint_line_text(painter, line_num)

    def check_draw_together(
        self, pre_char: pyte.screens.Char, char: pyte.screens.Char
    ) -> bool:
        return (
            pre_char.bg == char.bg
            and pre_char.fg == char.fg
            and pre_char.reverse == char.reverse
            and pre_char.bold == char.bold
            and pre_char.italics == char.italics
            and pre_char.underscore == char.underscore
            and pre_char.strikethrough == char.strikethrough
        )

    def draw_text(
        self,
        painter: QPainter,
        text: str,
        text_width: float,
        pre_char: pyte.screens.Char,
        start_x: float,
        start_y: float,
        is_two_width: bool,
    ):
        fg = "black" if pre_char.fg == "default" else pre_char.fg
        bg = "white" if pre_char.bg == "default" else pre_char.bg
        if self.theme_mode == "dark":
            fg = "white" if pre_char.fg == "default" else pre_char.fg
            bg = "black" if pre_char.bg == "default" else pre_char.bg
        if pre_char.reverse:
            fg, bg = bg, fg

        if text.strip() == "" and bg == "default":
            return

        style = []
        if pre_char.bold:
            style.append(StyleType.Bold)
        if pre_char.italics:
            style.append(StyleType.Italics)

        rect = QRectF(start_x, start_y, text_width, self.char_height)

        if bg != "default":
            painter.fillRect(rect, self.get_brush(bg))

        painter.setFont(self.get_font(style))
        painter.setPen(self.get_pen(fg))
        painter.drawText(rect, align, text)

        if pre_char.underscore:
            self.draw_line(painter, start_x, start_y, text_width, LineType.Underline)
        if pre_char.strikethrough:
            self.draw_line(painter, start_x, start_y, text_width, LineType.StrikeOut)

    def draw_line(
        self,
        painter: QPainter,
        start_x: float,
        start_y: float,
        width: float,
        line_type: LineType,
    ):
        if line_type == LineType.Underline:
            start_y += self.char_height - self.underline_pos
            line = QLineF(start_x, start_y, start_x + width, start_y)
            painter.drawLine(line)
        elif line_type == LineType.StrikeOut:
            start_y += self.char_height / 2
            line = QLineF(start_x, start_y, start_x + width, start_y)
            painter.drawLine(line)

    def paint_line_text(self, painter: QPainter, line_num: int):
        if line_num >= self.rows:
            return

        start_x = 0
        start_y = line_num * self.char_height
        screen = self.backend.screen

        clear_rect = QRectF(0, start_y, self.width(), self.char_height)
        painter.fillRect(clear_rect, self.get_brush("default"))

        all_background = set()

        line = screen.get_line(line_num)

        pre_char = pyte.screens.Char("")
        is_two_width = False
        real_is_two_width = False
        same_text = ""

        for col in range(screen.columns + 1):
            if col == screen.columns:
                char = None
            else:
                char = line[col]

            if char and char.data == "":
                continue

            if char and (line[col + 1].data == "" or line[col - 1].data == ""):
                is_two_width = True
            else:
                is_two_width = False
                real_is_two_width = False

            if char and self.check_draw_together(pre_char, char) and not is_two_width:
                same_text += char.data
                continue

            text_width = self.get_text_width(same_text, real_is_two_width)

            if char:
                all_background.add(char.bg)

            self.draw_text(
                painter,
                same_text,
                text_width,
                pre_char,
                start_x,
                start_y,
                real_is_two_width,
            )

            start_x += text_width

            if is_two_width:
                real_is_two_width = True

            if char:
                pre_char = char
                same_text = char.data

        if line_num == self.rows - 1:
            start_y += self.char_height
            height = self.height() - start_y
            brush = all_background.pop() if len(all_background) == 1 else "default"

            clear_rect = QRectF(0, start_y, self.width(), height)
            painter.fillRect(clear_rect, self.get_brush(brush))

    def paint_cursor(self, painter: QPainter):
        cursor = self.backend.cursor
        screen = self.backend.screen

        if cursor.hidden or screen.in_history:
            return

        self.cursor_x = cursor.x
        self.cursor_y = cursor.y

        line = screen.get_line(cursor.y)
        text_width = 0
        for col in range(cursor.x):
            char = line[col].data
            if char == "":
                continue
            text_width += self.get_text_width(char, line[col + 1].data == "")

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

    def paint_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_text(painter)
        self.paint_cursor(painter)

    def get_text_width(self, text: str, is_two_width=False):
        return self.char_width * 2 if is_two_width else self.fm.horizontalAdvance(text)

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

        self.backend.screen.exit_history()

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

        ratio = abs(y) / 200
        line_num = int(math.ceil(self.rows * ratio))

        if y > 0:
            self.backend.screen.scroll_up(line_num)
        else:
            self.backend.screen.scroll_down(line_num)

        self.update()

    @interactive
    def yank_text(self):
        text = get_emacs_func_result("eaf-pyqterminal-get-clipboard", ())
        if isinstance(text, str):
            self.send(text)

    @interactive
    def scroll_up(self):
        self.backend.screen.scroll_up(1)

    @interactive
    def scroll_down(self):
        self.backend.screen.scroll_down(1)

    @interactive
    def scroll_up_page(self):
        self.backend.screen.scroll_up(self.rows)

    @interactive
    def scroll_down_page(self):
        self.backend.screen.scroll_down(self.rows)

    @interactive
    def scroll_to_begin(self):
        self.backend.screen.scroll_up(self.backend.screen.base)

    @interactive
    def scroll_to_bottom(self):
        self.backend.screen.exit_history()
