# ZBookmarks

ZBookmarks is a small shortcut maker for Windows 10 and 11. You give it a web address or a folder, file or program path, give the shortcut a name, and it saves a standard Windows shortcut file for you. A website becomes a `.url` file. A path becomes a `.lnk` file. It is built with Python and wxPython, and it is designed to work well with screen readers and the keyboard.

Made by the zapps.ltd developers, Harith and Mesar, for ZAPPS SOFTWARE LTD.

## Why it exists

Making a shortcut by hand in Windows takes many steps: open a menu, pick a command, type or paste a location, name it, confirm. With a screen reader each step costs time. ZBookmarks reduces this to one window with two fields and one button. It can fill in the address and the name for you, so often you only need to press Enter.

## Features

Shortcut creation:

- Makes website shortcuts (`.url` files) for addresses that start with http://, https://, ftp:// or ftps://.
- Makes folder, file and program shortcuts (`.lnk` files) for paths that start with a drive letter and a backslash, or with a network path starting with two backslashes.
- Detects the shortcut type from what you type and tells you which kind it will make.
- Replaces characters Windows does not allow in file names (`\ / : * ? " < > |`) with an underscore.
- Uses the name "New Shortcut" if you leave the name empty.
- Asks before replacing a shortcut that already exists. It never overwrites silently.
- Shows the full path of the new shortcut in the status line, and shows an error message if creation fails.
- Saves to a folder named "Bookmarks and Shortcuts" on your Desktop by default, or to any folder you choose. The current save folder is always shown at the bottom of the window.

Filling in the fields:

- Pastes a URL or path from the clipboard when the app opens (it only pastes text that looks like a URL or a path). You can turn this off.
- Has a Paste button for the address field.
- Fetches the title of the web page and puts it in the name field, if the name is still empty. You can turn this off.
- Can read the address bar of the browser or File Explorer window you were just using, and fill in the address from it. It works with Chrome-based browsers (Chrome, Edge, Opera, Brave, Vivaldi, Chromium builds), Firefox, Internet Explorer and File Explorer. It copies the address with the keyboard and then puts your previous clipboard text back. You can turn this off.
- Pressing Enter in either field creates the shortcut.

Settings, hotkey and feedback:

- A first-run screen lets you choose the optional conveniences.
- Can put a ZBookmarks shortcut on your Desktop and give it a global hotkey, for example Ctrl+Alt+F. The hotkey is stored on that desktop shortcut by Windows, so it works only while the shortcut exists. Turning the option off removes the shortcut.
- Checks the hotkey format (letters, numbers and + only) before saving.
- Plays a short chime when a shortcut is created. You can turn this off.
- Can close itself after a successful creation. It stays open if creation fails.
- A More dialog opens the About, Tips and Tricks, and Privacy Policy pages in your default browser.
- Keeps a small local log file that helps to diagnose problems. It is limited to 256 KB. An Open log file button is in Settings.

## Accessibility

- All controls are reachable with Tab and work with Enter and Space.
- Fields have labels, and buttons and options have clear accessible names and descriptions, so NVDA, JAWS and Narrator announce them properly. The interface uses native Windows controls through wxPython, which screen readers read through MSAA and UI Automation.
- Tab order follows the reading order in every window and dialog, and focus starts in the address field.
- Results appear in a status line as text, and are not shown by colour alone.
- Dialogs can be closed with Escape where they offer it.
- The window uses a dark colour scheme with a clear focus outline on buttons, fields and options. Sighted users and keyboard-only users are supported equally with screen reader users.

If something does not work with your screen reader or your setup, please tell us (see Contact).

## Privacy

ZBookmarks does not collect, store or send any personal data or usage data. It has no analytics, no tracking and no accounts.

What it does on your computer:

- Settings are saved in a small JSON file in the `zbookmarks` folder inside your per-user application data folder (`%APPDATA%`).
- The log file is kept in the same folder. It can contain the addresses it handled. It never leaves your computer.
- Shortcuts are written only to the folder you choose.

The only network request it can make is to fetch the title of the page whose address you entered, when automatic title fetching is on. The request goes straight to that site and reads only the start of the page. Turn the option off to prevent it.

To do its work, the app starts Windows PowerShell in a hidden window to write shortcut files and to play the chime. It sends keystrokes to a browser or File Explorer window only for the address grab described above.

## Requirements

- Windows 10 or Windows 11. The app uses Windows features (shortcuts, PowerShell, the window system) and does not run on other systems.
- Windows PowerShell, which is part of Windows.
- To run from source: Python 3.10 or newer, and wxPython 4.3 or newer.

## Running from source

Install wxPython and start the app:

```
pip install wxPython
python zbookmarks.py
```

To make a single-file executable, install PyInstaller (`pip install pyinstaller`) and build `zbookmarks.py` as a windowed one-file app. Add `01.wav`, `about.html`, `tips.html` and `privacy.html` as data files in the program's root folder, and `icon.ico` as the icon if you want one. See the PyInstaller documentation for the exact options.

## Interface languages

The interface is in English only.

## Reporting problems and contact

Please report bugs, accessibility feedback and ideas by email to support@zapps.ltd or through the contact page of https://zapps.ltd, and describe your screen reader and Windows version. Pull requests are not accepted.

- Email: support@zapps.ltd
- Web: https://zapps.ltd

## License

ZBookmarks is free software, licensed under the GNU Affero General Public License, version 3 or (at your option) any later version (AGPL-3.0-or-later). The full text is in the file LICENSE. In short: you may use, study, change and share it, but every copy and every modified version, including one that other people use over a network, must stay under the same license, must come with its complete source code, and must keep the copyright notices and the credits below. Nobody can make a closed version of it. Copyright (C) 2026 ZAPPS SOFTWARE LTD.

## Third-party software and credits

ZBookmarks is built using:

- wxPython, by Robin Dunn, Scott Talbert and the wxPython contributors, and wxWidgets, by Julian Smart, Robert Roebling, Vadim Zeitlin and the wxWidgets team: wxWindows Library Licence 3.1 (https://wxpython.org, https://www.wxwidgets.org).
- Python, by the Python Software Foundation: PSF-2.0 (https://www.python.org).
- PyInstaller, used to build the executable: GPL-2.0-or-later with the bootloader exception (https://pyinstaller.org).

The full list and the license of each part are in the file THIRD_PARTY_NOTICES.md.
