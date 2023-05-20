;;; eaf-pyqterminal.el --- -*- lexical-binding: t -*-

;; Copyright (C) 2023 by Mumulhl <mumulhl@duck.com>
;; URL:
;; SPDX-License-Identifier: GPL-3.0-or-later

;;; Commentary:

;;; Code:

(defvar eaf-pyqterminal-path (file-name-directory load-file-name))

(defgroup eaf-pyqterminal nil
  "EAF PyQTerminal."
  :group 'eaf)

(defcustom eaf-pyqterminal-dark-mode "follow"
  "Dark mode of EAF pyqterminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-font-size 16
  "Font size of EAF pyqterminal."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-font-family ""
  "Font family of EAF pyqterminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-bell-sound-path (concat eaf-pyqterminal-path "bell.wav")
  "Bell sound path of EAF pyqterminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-color-schema
  ;; Tango Dark
  '(("background" "#000000")
    ("black" "#000000")
    ("blue" "#3465a4")
    ("brown" "#fce94f")
    ("cyan" "#06989a")
    ("cursor" "#ffffff")
    ("foreground" "#ffffff")
    ("green" "#4e9a06")
    ("magenta" "#75507b")
    ("red" "#cc0000")
    ("yellow" "#c4a000")
    ("white" "#d3d7cf")
    ("brightblack" "#555753")
    ("brightblue" "#729fcf")
    ("brightcyan" "#34e2e2")
    ("brightgreen" "#8ae234")
    ("brightmagenta" "#ad7fa8")
    ("brightred" "#ef2929")
    ("brightwhite" "#eeeeec")
    ("brightyellow" "#fce94f"))
  "Color schema for EAF pyqterminal."
  :type 'alist
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-keybinding
  '(("C-S-v" . "yank_text")
    ("C-a" . "eaf-send-key-sequence")
    ("C-e" . "eaf-send-key-sequence")
    ("C-f" . "eaf-send-key-sequence")
    ("C-b" . "eaf-send-key-sequence")
    ("C-d" . "eaf-send-key-sequence")
    ("C-n" . "eaf-send-key-sequence")
    ("C-p" . "eaf-send-key-sequence")
    ("C-r" . "eaf-send-key-sequence")
    ("C-k" . "eaf-send-key-sequence")
    ("C-o" . "eaf-send-key-sequence")
    ("C-u" . "eaf-send-key-sequence")
    ("C-l" . "eaf-send-key-sequence")
    ("C-w" . "eaf-send-key-sequence")
    ("C-g" . "eaf-send-key-sequence")
    ("M-f" . "eaf-send-key-sequence")
    ("M-b" . "eaf-send-key-sequence")
    ("M-d" . "eaf-send-key-sequence")
    ("C-c C-c" . "eaf-send-second-key-sequence")
    ("C-c C-x" . "eaf-send-second-key-sequence")
    ("C-y" . "yank_text")
    ("M-DEL" . "eaf-send-alt-backspace-sequence")
    ("M-<backspace>" . "eaf-send-alt-backspace-sequence")
    ("<escape>" . "eaf-send-escape-key"))
  "The keybinding of EAF Terminal."
  :type 'cons)

(add-to-list
 'eaf-app-binding-alist '("pyqterminal" . eaf-pyqterminal-keybinding))

(defvar eaf-pyqterminal-module-path
  (concat eaf-pyqterminal-path "buffer.py"))
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
    (puthash "directory" expand-dir args)
    (eaf-open dir "pyqterminal" (json-encode-hash-table args) always-new)))

(defun eaf-pyqterminal-get-clipboard ()
  "Get clipboard text."
  (let* ((source-data (gui-get-selection 'CLIPBOARD)))
    (set-text-properties 0 (length source-data) nil source-data)
    source-data))

;;;###autoload
(defun eaf-open-pyqterminal ()
  "Open EAF PyQTerminal."
  (interactive)
  (eaf-pyqterminal-run-command-in-dir
   (getenv "SHELL") (eaf--non-remote-default-directory)
   t))

;;;###autoload
(defun eaf-open-ipython ()
  "Open ipython by EAF PyQTerminal."
  (interactive)
  (eaf-pyqterminal-run-command-in-dir
   "ipython" (eaf--non-remote-default-directory)
   t))

(provide 'eaf-pyqterminal)
;;; eaf-pyqterminal.el ends here
