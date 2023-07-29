;;; eaf-pyqterminal.el --- -*- lexical-binding: t -*-

;; Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
;; SPDX-License-Identifier: GPL-3.0-or-later

;;; Commentary:

;;; Code:

(defvar eaf-pyqterminal-path (file-name-directory load-file-name))

(defgroup eaf-pyqterminal nil
  "EAF PyQterminal."
  :group 'eaf)

(defcustom eaf-pyqterminal-font-size 16
  "Font size of EAF PyQterminal."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-font-family ""
  "Font family of EAF PyQterminal, we will use system Mono font if user choose font is not exist.

Recommend use Nerd font to render icon in terminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-refresh-ms 17
  "Maybe you need to set this variable when you change the repeat rate."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-type "box"
  "Type of cursor.

You can set this variable to `box', `bar' and `hbar'."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-size 2
  "Setting the cursor size for the `bar' or `hbar' cursor types."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-alpha -1
  "Alpha of cursor.

If alpha < 0, don't set alpha for cursor."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-color-schema
  ;; Tango Dark
  '(("blue" "#3465a4")
    ("brown" "#fce94f")
    ("cyan" "#06989a")
    ("cursor" "#eeeeec")
    ("green" "#4e9a06")
    ("magenta" "#75507b")
    ("red" "#cc0000")
    ("yellow" "#c4a000")
    ("brightblack" "#555753")
    ("brightblue" "#729fcf")
    ("brightcyan" "#34e2e2")
    ("brightgreen" "#8ae234")
    ("brightmagenta" "#ad7fa8")
    ("brightred" "#ef2929")
    ("brightwhite" "#eeeeec")
    ("brightyellow" "#fce94f"))
  "Color schema for EAF PyQterminal."
  :type 'alist
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-keybinding
  '(("C-S-v" . "yank_text")
    ("C-a" . "eaf-send-key-sequence")
    ("C-b" . "eaf-send-key-sequence")
    ("C-c C-c" . "eaf-send-second-key-sequence")
    ("C-c C-x" . "eaf-send-second-key-sequence")
    ("C-c C-m" . "eaf-send-second-key-sequence")
    ("C-d" . "eaf-send-key-sequence")
    ("C-e" . "eaf-send-key-sequence")
    ("C-f" . "eaf-send-key-sequence")
    ("C-g" . "eaf-send-key-sequence")
    ("C-h" . "eaf-send-key-sequence")
    ("C-j" . "eaf-send-key-sequence")
    ("C-k" . "eaf-send-key-sequence")
    ("C-l" . "eaf-send-key-sequence")
    ("C-n" . "eaf-send-key-sequence")
    ("C-o" . "eaf-send-key-sequence")
    ("C-p" . "eaf-send-key-sequence")
    ("C-r" . "eaf-send-key-sequence")
    ("C-s" . "eaf-send-key-sequence")
    ("C-t" . "eaf-send-key-sequence")
    ("C-u" . "eaf-send-key-sequence")
    ("C-v" . "scroll_down_page")
    ("C-w" . "eaf-send-key-sequence")
    ("C-y" . "yank_text")
    ("C-z" . "eaf-send-key-sequence")
    ("M-f" . "eaf-send-key-sequence")
    ("M-b" . "eaf-send-key-sequence")
    ("M-d" . "eaf-send-key-sequence")
    ("M-c" . "toggle_cursor_move_mode")
    ("M-k" . "scroll_up")
    ("M-j" . "scroll_down")
    ("M-v" . "scroll_up_page")
    ("M-<" . "scroll_to_begin")
    ("M->" . "scroll_to_bottom")
    ("M-w" . "copy_text")
    ("M-DEL" . "eaf-send-alt-backspace-sequence")
    ("M-<backspace>" . "eaf-send-alt-backspace-sequence")
    ("C-M-f" . "open_link")
    ("<escape>" . "eaf-send-escape-key"))
  "The keybinding of EAF PyQterminal."
  :type 'cons)

(defcustom eaf-pyqterminal-cursor-move-mode-keybinding
  '(("j" . "next_line")
    ("k" . "previous_line")
    ("l" . "next_character")
    ("h" . "previous_character")
    ("e" . "next_word")
    ("E" . "next_symbol")
    ("b" . "previous_word")
    ("B" . "previous_symbol")
    ("J" . "scroll_down")
    ("K" . "scroll_up")
    ("H" . "move_beginning_of_line")
    ("L" . "move_end_of_line")
    ("d" . "scroll_down_page")
    ("u" . "scroll_up_page")
    ("v" . "toggle_mark")
    ("y" . "copy_text")
    ("i" . "copy_word")
    ("I" . "copy_symbol")
    ("f" . "open_link")
    ("q" . "toggle_cursor_move_mode")
    ("C-a" . "move_beginning_of_line")
    ("C-e" . "move_end_of_line")
    ("C-n" . "next_line")
    ("C-p" . "previous_line")
    ("C-f" . "next_character")
    ("C-b" . "previous_character")
    ("C-v" . "scroll_down_page")
    ("M-f" . "next_word")
    ("M-F" . "next_symbol")
    ("M-b" . "previous_word")
    ("M-B" . "previous_symbol")
    ("M-v" . "scroll_up_page")
    ("M-c" . "toggle_cursor_move_mode")
    ("M-w" . "copy_text")
    ("M-d" . "copy_word")
    ("M-D" . "copy_symbol")
    ("C-SPC" . "toggle_mark")
    ("C-M-f" . "open_link"))
  "The keybinding of EAF PyQterminal Cursor Move Mode.

Cursor Move Mode allows you to move cursor in the screen."
  :type 'cons)

(add-to-list
 'eaf-app-binding-alist '("pyqterminal" . eaf-pyqterminal-keybinding))

(defvar eaf-pyqterminal-module-path
  (concat eaf-pyqterminal-path "eaf_pyqterm_buffer.py"))
(add-to-list
 'eaf-app-module-path-alist '("pyqterminal" . eaf-pyqterminal-module-path))

(defun eaf-send-second-key-sequence ()
  "Send second part of key sequence to terminal."
  (interactive)
  (eaf-call-async
   "send_key_sequence"
   eaf--buffer-id
   (nth 1 (split-string (key-description (this-command-keys-vector))))))

(defun eaf-pyqterminal-run-command-in-dir (command dir &optional always-new)
  "Run COMMAND in terminal in directory DIR.

If ALWAYS-NEW is non-nil, always open a new terminal for the dedicated DIR."
  (let* ((args (make-hash-table :test 'equal))
         (expand-dir (expand-file-name dir)))
    (puthash "command" command args)
    (puthash
     "directory"
     (if (eaf--called-from-wsl-on-windows-p)
         (eaf--translate-wsl-url-to-windows expand-dir)
       expand-dir)
     args)
    (eaf-open dir "pyqterminal" (json-encode-hash-table args) always-new)))

(defun eaf--generate-terminal-command ()
  (if (or (eaf--called-from-wsl-on-windows-p) (eq system-type 'windows-nt))
      "powershell.exe"
    (getenv "SHELL")))

(defun eaf-ipython-command ()
  (if (eaf--called-from-wsl-on-windows-p)
      "ipython.exe"
    "ipython"))

(defun eaf--toggle-cursor-move-mode (status)
  "Toggle Cursor Move Mode."
  (if status
      (eaf--gen-keybinding-map eaf-pyqterminal-cursor-move-mode-keybinding t)
    (eaf--gen-keybinding-map eaf-pyqterminal-keybinding))
  (setq eaf--buffer-map-alist (list (cons t eaf-mode-map))))

;;;###autoload
(defun eaf-open-pyqterminal ()
  "Open EAF PyQterminal."
  (interactive)
  (eaf-pyqterminal-run-command-in-dir
   (eaf--generate-terminal-command) (eaf--non-remote-default-directory)
   t))

;;;###autoload
(defun eaf-open-ipython ()
  "Open ipython by EAF PyQterminal."
  (interactive)
  (if (executable-find (eaf-ipython-command))
      (eaf-pyqterminal-run-command-in-dir
       (eaf-ipython-command) (eaf--non-remote-default-directory)
       t)
    (message "[EAF/terminal] Please install ipython first.")))

(provide 'eaf-pyqterminal)
;;; eaf-pyqterminal.el ends here
