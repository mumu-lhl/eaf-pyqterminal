# Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import time
from enum import Enum

import pyte
from core.buffer import interactive
from core.utils import *
from PyQt6.QtCore import QEvent, QLineF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QKeyEvent,
    QPainter,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QWidget
from pyte.screens import Cursor

import eaf_pyqterm_backend as backend
from eaf_pyqterm_utils import generate_random_key, match_link

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


class FrontendWidget(QWidget):
    color_map = {}
    fonts = {}

    def __init__(self, argv, start_directory):
        super().__init__()

        (
            self.font_size,
            self.font_family,
            self.refresh_ms,
            self.cursor_type,
            self.cursor_size,
            self.cursor_alpha,
            self.device_pixel_ratio,
            self.marker_letters,
        ) = get_emacs_vars(
            (
                "eaf-pyqterminal-font-size",
                "eaf-pyqterminal-font-family",
                "eaf-pyqterminal-refresh-ms",
                "eaf-pyqterminal-cursor-type",
                "eaf-pyqterminal-cursor-size",
                "eaf-pyqterminal-cursor-alpha",
                "eaf-pyqterminal-device-pixel-ratio",
                "eaf-marker-letters",
            )
        )

        self.ensure_font_exist()

        self.installEventFilter(self)

        self.init_color_schema()

        self.directory = ""
        self.title = ""

        self.link_markers: dict[str, str] = {}
        self.link_markers_position: list[int] = []

        self.last_mouse_click_time = 0
        self.last_mouse_click_position = (0, 0)
        self.first_mouse_move = True

        self.cursor = Cursor(0, 0)

        font = QFont()
        font.setFamily(self.font_family)
        font.setPixelSize(self.font_size)
        fm = QFontMetricsF(font)
        self.font = font
        self.char_height = fm.height()
        self.char_width = fm.horizontalAdvance("W")
        screen = QApplication.instance().primaryScreen()    # type: ignore
        self.columns, self.rows = self.pixel_to_position(screen.size().width(), screen.size().height())
        self.underline_pos = fm.underlinePos()

        self.backend = backend.Backend(self.columns, self.rows, argv, start_directory)

        self.init_pixmap()

        self.startTimer(self.refresh_ms)

    def ensure_font_exist(self):
        """Use system Mono font if user's font is not exist."""
        if self.font_family not in QFontDatabase.families():
            self.font_family = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            ).family()

    def init_color_schema(self):
        color_schema = get_emacs_func_result("eaf-pyqterminal-get-color-schema", [])

        for name, color in color_schema:
            self.color_map[name] = color

        theme_mode = get_emacs_theme_mode()
        theme_background_color = get_emacs_theme_background()
        if theme_mode == "dark":
            self.color_map["white"] = "#FFFFFF"
        else:
            self.color_map["white"] = "#000000"
        self.color_map["black"] = theme_background_color

    def init_pixmap(self):
        self.pixmap = QPixmap(
            self.width() * self.device_pixel_ratio,
            self.height() * self.device_pixel_ratio,
        )
        self.pixmap.setDevicePixelRatio(self.device_pixel_ratio)

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

    def pixel_to_position(self, x: int, y: int) -> tuple[int, int]:
        column = int(x / self.char_width)
        row = int(y / self.char_height)
        return column, row

    def paint_text(self, painter: QPainter):
        screen = self.backend.screen

        # Redraw the old and new cursor's line
        screen.dirty.update([self.cursor.y, screen.get_cursor().y])

        # Dirty will change when traversing
        while screen.dirty:
            y = screen.dirty.pop()
            self.paint_text_of_line(painter, y)

    def draw_text(
        self,
        painter: QPainter,
        text: str,
        text_width: float,
        pre_char: pyte.screens.Char,
        start_x: float,
        start_y: float,
        is_selection: bool,
    ):
        fg = pre_char.fg
        bg = pre_char.bg
        if bg == "default" and text.strip() == "":
            return
        if fg == "default":
            fg = "white"
        if bg == "default":
            bg = "black"

        if pre_char.reverse:
            fg, bg = bg, fg

        if is_selection:
            fg = "black"
            bg = "white"

        style = []
        if pre_char.bold:
            style.append(StyleType.Bold)
        if pre_char.italics:
            style.append(StyleType.Italics)

        rect = QRectF(start_x, start_y, text_width, self.char_height)
        painter.fillRect(rect, QColor(self.color_map.get(bg) or "#" + bg))

        painter.setFont(self.get_font(style))
        painter.setPen(QColor(self.color_map.get(fg) or "#" + fg))
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

    def can_draw_together(
        self,
        pre_char: pyte.screens.Char,
        char: pyte.screens.Char,
        is_selection: bool,
        pre_is_selection: bool,
        is_two_width: bool,
    ) -> bool:
        is_fg_same = True if pre_is_selection else pre_char.fg == char.fg
        is_bg_same = True if pre_is_selection else pre_char.bg == char.bg

        return (
            is_fg_same
            and is_bg_same
            and not is_two_width
            and not pre_is_selection
            and pre_is_selection == is_selection
            and pre_char.reverse == char.reverse
            and pre_char.bold == char.bold
            and pre_char.italics == char.italics
            and pre_char.underscore == char.underscore
            and pre_char.strikethrough == char.strikethrough
        )

    def clear_line(self, painter: QPainter, y: float):
        clear_rect = QRectF(0, y, self.width(), self.char_height)
        painter.fillRect(clear_rect, QColor(self.color_map["black"]))

    def paint_text_of_line(self, painter: QPainter, row: int):
        if row >= self.rows:
            return

        char_height = self.char_height
        char_width = self.char_width

        x = 0
        y = row * char_height

        screen = self.backend.screen
        line = screen.get_line(row)

        selection = screen.get_selection(row)
        is_two_width = True
        same_text = ""

        pre_char = pyte.screens.Char("")
        pre_is_selection = 0 in selection

        self.clear_line(painter, y)

        text_width = 0
        for column in range(screen.columns + 1):
            char = line[column]

            text_width += char_width
            if column < screen.columns:
                if char.data == "":
                    continue

                is_selection = column in selection
                is_two_width = line[column + 1].data == ""

                if self.can_draw_together(
                    pre_char,
                    char,
                    is_selection,
                    pre_is_selection,
                    is_two_width,
                ):
                    same_text += char.data
                    continue

            self.draw_text(
                painter,
                same_text,
                text_width,
                pre_char,
                x,
                y,
                pre_is_selection,
            )
            if column != 0:
                x += text_width
            text_width = 0

            pre_char = char
            same_text = char.data
            pre_is_selection = is_selection

        if row == self.rows - 1:
            y += char_height
            self.clear_line(painter, y)

    def paint_cursor(self, painter: QPainter):
        screen = self.backend.screen
        cursor = screen.get_cursor()

        if cursor.hidden or (screen.in_history and not screen.cursor_move_mode):
            return

        self.cursor.x = cursor.x
        self.cursor.y = cursor.y
        self.cursor.hidden = cursor.hidden

        line = screen.get_line(cursor.y)
        cursor_x = 0
        cursor_y = cursor.y * self.char_height
        char_width = self.char_width
        cursor_x += char_width * cursor.x

        cursor_height = self.char_height
        cursor_alpha = self.cursor_alpha
        cursor_width = (
            self.char_width * 2 if line[cursor.x + 1].data == "" else self.char_width
        )
        if (
            self.cursor_type == "box"
            and line[cursor.x].data != " "
            and cursor_alpha < 0
        ):
            cursor_alpha = 110
        elif self.cursor_type == "bar":
            cursor_height = self.cursor_size
            cursor_y += self.char_height - cursor_height
        elif self.cursor_type == "hbar":
            cursor_width = self.cursor_size

        if screen.marker and not screen.mouse:
            brush = self.color_map["yellow"]
        else:
            brush = self.color_map["cursor"]
        brush = QColor(brush)
        if cursor_alpha != -1:
            brush.setAlpha(cursor_alpha)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRect(QRectF(cursor_x, cursor_y, cursor_width, cursor_height))

    def paint_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_text(painter)
        self.paint_cursor(painter)

    def get_text_width(self, text: str, is_two_width: bool = False) -> float:
        if is_two_width:
            return self.char_width * 2
        else:
            return self.char_width * len(text)

    def focusProxy(self):
        return self

    @PostGui()
    def handle_input_response(self, callback_tag: str, result_content: str):
        if callback_tag == "open_link":
            self._open_link(result_content)

    @PostGui()
    def cancel_input_response(self, callback_tag: str):
        if callback_tag == "open_link":
            self.cleanup_link_markers()

    def fetch_marker_callback(self) -> list[str]:
        key_list = list(self.link_markers.keys())
        return list(map(lambda key: key.lower(), key_list))

    def render_marker(self, markers: dict[str, dict[str, str]]):
        painter = QPainter(self.pixmap)
        painter.setPen(QColor(self.color_map["black"]))
        for y, markers in markers.items():
            line = self.backend.screen.get_line(y)
            x_position, y_position = 0, y * self.char_height
            x_display = 0
            for x in range(self.columns):
                char = line[x].data
                if char == "":
                    continue
                x_display += 1
                x_position += self.get_text_width(char, line[x + 1].data == "")

                marker = markers.get(0 if x == 0 else x_display)
                if marker:
                    rect = QRectF(
                        0 if x == 0 else x_position,
                        y_position,
                        self.get_text_width(marker),
                        self.char_height,
                    )
                    painter.fillRect(rect, QColor(self.color_map["yellow"]))
                    painter.drawText(rect, align, marker)
                    self.update()

    def get_link_markers(self):
        text = ""
        count = 0
        links = {}
        continue_line = False
        screen = self.backend.screen

        for y in range(0, self.rows):
            line = screen.get_line_display(y)
            line_strip = line.rstrip()
            old_continue_line = continue_line
            continue_line = line == line_strip
            if (
                old_continue_line != continue_line
                or old_continue_line == continue_line is False
            ):
                links_in_line, count_in_line = match_link(text)
                links[y - 1] = links_in_line
                count += count_in_line
                text = ""
            if continue_line:
                text += line_strip
            else:
                text = line_strip

        if count == 0:
            message_to_emacs("No link found")
            return

        key_list = generate_random_key(count, self.marker_letters)
        markers = {}
        count = 0
        for y, links in links.items():
            if links:
                markers[y] = {}
            for x, link in links.items():
                key = key_list[count]
                self.link_markers[key] = link
                if x >= self.columns:
                    line_down_number = x // self.columns
                    x -= line_down_number * self.columns
                    y += line_down_number
                    markers[y].update({x: key})
                    count += 1
                    self.link_markers_position = list(markers.keys())

        self.render_marker(markers)

    @PostGui()
    def cleanup_link_markers(self):
        self.link_markers = {}
        # Doing so because can't direct update screen dirty
        painter = QPainter(self.pixmap)
        for y in self.link_markers_position:
            self.paint_text_of_line(painter, y)
            self.update()

    def _open_link(self, marker: str):
        link = self.link_markers.get(marker.upper())
        if link:
            open_url_in_new_tab(link)
            self.cleanup_link_markers()

    def get_cursor_absolute_position(self) -> tuple[int, int]:
        pos = self.mapFromGlobal(QCursor.pos())
        return pos.x(), pos.y()

    def resize_view(self):
        width = self.width()
        height = self.height()

        self.columns, self.rows = self.pixel_to_position(width, height)
        self.backend.resize(self.columns, self.rows)

        self.init_pixmap()
        self.paint_pixmap()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)

    @PostGui()
    def timerEvent(self, _):
        screen = self.backend.screen
        cursor = screen.get_cursor()

        if (
            not screen.dirty
            and not screen.cursor_dirty
            and self.cursor.x == cursor.x
            and self.cursor.y == cursor.y
            and self.cursor.hidden == cursor.hidden
        ):
            return

        if (
            screen.cursor_dirty
            and self.cursor.x == cursor.x
            and self.cursor.y == cursor.y
        ):
            painter = QPainter(self.pixmap)
            screen.cursor_dirty = False
            self.paint_cursor(painter)
            self.update()
        else:
            self.paint_pixmap()
            self.update()

        title = self.backend.title()
        if title != self.title:
            self.title = title
            self.change_title(f"Term [{title}]")

        directory = self.backend.getcwd()
        if directory and directory != self.directory:
            self.directory = directory
            eval_in_emacs("eaf--change-default-directory", [self.buffer_id, directory])

    def keyPressEvent(self, event: QKeyEvent):
        text = str(event.text())
        key = event.key()
        modifier = event.modifiers()
        s = KEY_DICT.get(key)

        if self.backend.screen.cursor_move_mode:
            return

        self.backend.screen.scroll_to_bottom()

        send = self.backend.send

        if (text or s) and modifier == Qt.KeyboardModifier.ControlModifier:
            # 'a' => '\x01', 'A' => '\x01'
            try:
                text = chr(ord(text.lower()) - 96)
            except:
                pass

            send(text)
            return
        if (text or s) and modifier == Qt.KeyboardModifier.AltModifier:
            text = s if s else text
            send(pyte.control.ESC + text)
            return

        if text and not s:
            send(text)
            return

        if s:
            event.accept()
            send(s)

    def wheelEvent(self, event: QWheelEvent):
        y = event.angleDelta().y()

        ratio = abs(y) / 200
        line_num = int(math.ceil(self.rows * ratio))

        if y > 0:
            self.backend.screen.scroll_up(line_num)
        else:
            self.backend.screen.scroll_down(line_num)

        self.update()

    def auto_scroll(self, y):
        screen = self.backend.screen
        if y < 0 and screen.auto_scroll_lock:
            screen.auto_scroll_up()
        elif y > self.height() and screen.auto_scroll_lock:
            screen.auto_scroll_down()
        elif 0 < y < self.height() and screen.current_thread:
            screen.disable_auto_scroll()

    def eventFilter(self, _, event: QEvent):
        screen = self.backend.screen

        if event.type() == QEvent.Type.MouseButtonPress:
            x, y = self.get_cursor_absolute_position()
            column, row = self.pixel_to_position(x, y)
            screen.move_to_position(column, row)
            self.last_mouse_click_time = time.time()
            self.last_mouse_click_position = (x, y)

            if screen.cursor_move_mode:
                screen.before_is_cursor_move_mode = True

                if screen.marker:
                    screen.toggle_mark()
                if screen.marker:
                    screen.toggle_mark()

            self.grabMouse()
        elif event.type() == QEvent.Type.MouseMove:
            x, y = self.get_cursor_absolute_position()
            column, row = self.pixel_to_position(x, y)
            if y < 0:
                row = -1
                screen.move_to_position(column, row)
                screen.absolute_virtual_cursor_y = screen.base + row

            if self.first_mouse_move:
                self.first_mouse_move = False
                screen.before_is_cursor_move_mode = screen.cursor_move_mode
                self.toggle_cursor_move_mode(True)
                screen.set_marker(column, row)

                if not screen.before_is_cursor_move_mode:
                    screen.mouse = True

            self.auto_scroll(y)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self.first_mouse_move = True

            if screen.current_thread:
                screen.disable_auto_scroll()

            x, y = self.get_cursor_absolute_position()

            if not screen.before_is_cursor_move_mode:
                screen.fake_marker = True
                screen.cursor_move_mode = False
                screen.sync_cursor()

                eval_in_emacs("eaf--toggle-cursor-move-mode", ["'nil"])

            self.releaseMouse()

        return False

    @interactive
    def yank_text(self):
        text = get_clipboard_text()
        self.backend.send(text)

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
        self.backend.screen.scroll_to_begin()

    @interactive
    def scroll_to_bottom(self):
        self.backend.screen.scroll_to_bottom()

    @interactive
    def next_line(self):
        self.backend.screen.next_line()

    @interactive
    def previous_line(self):
        self.backend.screen.previous_line()

    @interactive
    def next_character(self):
        self.backend.screen.next_character()

    @interactive
    def previous_character(self):
        self.backend.screen.previous_character()

    @interactive
    def next_word(self):
        self.backend.screen.next_thing("word")

    @interactive
    def previous_word(self):
        self.backend.screen.previous_thing("word")

    @interactive
    def next_symbol(self):
        self.backend.screen.next_thing("symbol")

    @interactive
    def previous_symbol(self):
        self.backend.screen.previous_thing("symbol")

    @interactive
    def move_beginning_of_line(self):
        self.backend.screen.move_beginning_of_line()

    @interactive
    def move_end_of_line(self):
        self.backend.screen.move_end_of_line()

    @interactive
    def toggle_mark(self):
        screen = self.backend.screen
        screen.toggle_mark()
        message_to_emacs("Mark set" if screen.marker else "Mark deactivated")

    @interactive
    def toggle_cursor_move_mode(self, status=None):
        self.backend.screen.toggle_cursor_move_mode(status)

    @interactive
    def copy_text(self):
        self.backend.screen.copy_thing("selection")

    @interactive
    def copy_word(self):
        self.backend.screen.copy_thing("word")

    @interactive
    def copy_symbol(self):
        self.backend.screen.copy_thing("symbol")

    @interactive
    def open_link(self):
        self.get_link_markers()
        if self.link_markers:
            self.send_input_message("Open Link: ", "open_link", "marker")
