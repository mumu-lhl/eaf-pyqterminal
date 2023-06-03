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

(defcustom eaf-pyqterminal-font-size 16
  "Font size of EAF pyqterminal."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-font-family ""
  "Font family of EAF pyqterminal, we will use system Mono font if user choose font is not exist.

Recommend use Nerd font to render icon in terminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-bell-sound-path
  (concat eaf-pyqterminal-path "bell.ogg")
  "Bell sound path of EAF pyqterminal."
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-refresh-ms 100
  "Maybe need to set this variable when you change repeat rate."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-type "box"
  "Type of cursor.

You can set this variable to `box', `bar' and `hbar'"
  :type 'string
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-size 2
  "Setting cursor size for the cursor type of `bar' or `hbar'."
  :type 'integer
  :group 'eaf-pyqterminal)

(defcustom eaf-pyqterminal-cursor-alpha -1
  "Alpha of cursor.

If alpha < 0, don't set alpha for cursor"
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
  "Color schema for EAF pyqterminal."
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
    ("C-v" . "eaf-send-key-sequence")
    ("C-w" . "eaf-send-key-sequence")
    ("C-y" . "yank_text")
    ("C-z" . "eaf-send-key-sequence")
    ("M-f" . "eaf-send-key-sequence")
    ("M-b" . "eaf-send-key-sequence")
    ("M-d" . "eaf-send-key-sequence")
    ("C-m" . "eaf-send-return-key")
    ("M-DEL" . "eaf-send-alt-backspace-sequence")
    ("M-<backspace>" . "eaf-send-alt-backspace-sequence")
    ("<escape>" . "eaf-send-escape-key"))
  "The keybinding of EAF Terminal."
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

(defun eaf-send-return-key ()
  (interactive)
  (eaf-call-async "send_key" eaf--buffer-id "<return>"))

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

(defun eaf-pyqterminal-get-clipboard ()
  "Get clipboard text."
  (let* ((source-data (current-kill 0)))
    (set-text-properties 0 (length source-data) nil source-data)
    source-data))

(defun eaf--generate-terminal-command ()
  (if (or (eaf--called-from-wsl-on-windows-p) (eq system-type 'windows-nt))
      "powershell.exe"
    (getenv "SHELL")))

(defun eaf-ipython-command ()
  (if (eaf--called-from-wsl-on-windows-p)
      "ipython.exe"
    "ipython"))

;;;###autoload
(defun eaf-open-pyqterminal ()
  "Open EAF PyQTerminal."
  (interactive)
  (eaf-pyqterminal-run-command-in-dir
   (eaf--generate-terminal-command) (eaf--non-remote-default-directory)
   t))

;;;###autoload
(defun eaf-open-ipython ()
  "Open ipython by EAF PyQTerminal."
  (interactive)
  (if (executable-find (eaf-ipython-command))
      (eaf-pyqterminal-run-command-in-dir
       (eaf-ipython-command) (eaf--non-remote-default-directory)
       t)))

(provide 'eaf-pyqterminal)
;;; eaf-pyqterminal.el ends here
))

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

(defun eaf-pyqterminal-get-clipboard ()
  "Get clipboard text."
  (let* ((source-data (current-kill 0)))
    (set-text-properties 0 (length source-data) nil source-data)
    source-data))

(defun eaf--generate-terminal-command ()
  (if (or (eaf--called-from-wsl-on-windows-p) (eq system-type 'windows-nt))
      "powershell.exe"
    (getenv "SHELL")))

(defun eaf-ipython-command ()
  (if (eaf--called-from-wsl-on-windows-p)
      "ipython.exe"
    "ipython"))

;;;###autoload
(defun eaf-open-pyqterminal ()
  "Open EAF PyQTerminal."
  (interactive)
  (eaf-pyqterminal-run-command-in-dir
   (eaf--generate-terminal-command) (eaf--non-remote-default-directory)
   t))

;;;###autoload
(defun eaf-open-ipython ()
  "Open ipython by EAF PyQTerminal."
  (interactive)
  (if (executable-find (eaf-ipython-command))
      (eaf-pyqterminal-run-command-in-dir
       (eaf-ipython-command) (eaf--non-remote-default-directory)
       t)))

(provide 'eaf-pyqterminal)
;;; eaf-pyqterminal.el ends here
