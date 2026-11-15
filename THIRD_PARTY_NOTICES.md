# Third-party notices

ZBookmarks is licensed under AGPL-3.0-or-later (see LICENSE). It uses the third-party components below. Each keeps its own license and copyright. Nothing here changes those licenses.

Copyright of ZBookmarks: (C) 2026 ZAPPS SOFTWARE LTD.

## Components

wxPython
- Author: Robin Dunn, Scott Talbert and the wxPython contributors.
- Use: the Python bindings for wxWidgets. They provide every window, field, button and dialog.
- License: wxWindows Library Licence, version 3.1: the GNU Library General Public Licence, version 2 or later, with an exception that allows works based on the library to be distributed in binary form under the user's own terms.
- URL: https://wxpython.org
- Source code: https://github.com/wxWidgets/Phoenix

wxWidgets (the wxbase and wxmsw libraries that come with wxPython)
- Author: Julian Smart, Robert Roebling, Vadim Zeitlin and the wxWidgets team.
- Use: the user interface toolkit. It uses the native Windows controls, which screen readers read through MSAA and UI Automation.
- License: wxWindows Library Licence, version 3.1. Some third-party libraries built into wxWidgets (for example zlib, libpng, libjpeg and libtiff) keep their own permissive licenses.
- URL: https://www.wxwidgets.org
- Source code: https://github.com/wxWidgets/wxWidgets

Python
- Author: the Python Software Foundation and contributors.
- Use: the language runtime that runs ZBookmarks, including its standard library. An executable build contains a copy of it.
- License: PSF-2.0 (Python Software Foundation License, version 2). Parts of the standard library carry other permissive licenses; see the Python license page.
- URL: https://www.python.org
- License text: https://docs.python.org/3/license.html

OpenSSL (inside the Python runtime)
- Author: the OpenSSL Project.
- Use: secure connections (https) when the app fetches a page title. It is part of the Python Windows build and is included in an executable that bundles Python.
- License: Apache-2.0 (version 3.x of OpenSSL).
- URL: https://www.openssl.org

PyInstaller (build tool, only for the executable)
- Author: the PyInstaller Development Team.
- Use: packs the program, Python and the libraries into one `.exe`. Its small loader program (bootloader) becomes part of the executable.
- License: GPL-2.0-or-later WITH the Bootloader exception. The exception lets programs packed with PyInstaller be distributed under any license.
- URL: https://pyinstaller.org

Microsoft Visual C++ runtime (vcruntime and related DLLs, in an executable build)
- Author: Microsoft.
- Use: the C runtime that Python and wxWidgets need on Windows.
- License: Microsoft redistributable terms, shipped as a system library.
- URL: https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files

UPX (optional build tool)
- Author: Markus Oberhumer, Laszlo Molnar and John Reiser.
- Use: if it is installed on the build machine, PyInstaller may use it to compress the executable. Then its decompression stub is in the executable.
- License: GPL-2.0-or-later WITH the UPX stub exception.
- URL: https://upx.github.io

Windows components used at run time, not shipped: Windows PowerShell, the WScript.Shell COM object and the Windows shell and window APIs. They are part of Windows and are used through ordinary system interfaces.

## Assets

- icon.ico (application icon) and 01.wav (success chime): the project's own work, covered by the license of ZBookmarks (AGPL-3.0-or-later).
- No font is bundled. The interface asks Windows for Segoe UI, which Windows provides.

## wxPython and wxWidgets in an executable

The exception in the wxWindows Library Licence allows ZBookmarks to be distributed as an executable that contains wxPython and wxWidgets, under the license of ZBookmarks, with no further conditions on the executable. Their complete source code is at the addresses above. Changes to wxPython or wxWidgets themselves, when distributed as source, stay under the wxWindows Library Licence.

## License texts that must accompany copies

- wxWindows Library Licence 3.1 for wxPython and wxWidgets: https://www.wxwidgets.org/about/licence/
- GNU Library General Public Licence version 2, which it builds on: https://www.gnu.org/licenses/old-licenses/lgpl-2.0.txt
- PSF-2.0 for Python: https://docs.python.org/3/license.html
- Apache-2.0 for OpenSSL: https://www.apache.org/licenses/LICENSE-2.0.txt
- PyInstaller bootloader exception: https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

Notice required by the Python license: Python is Copyright (c) 2001 Python Software Foundation, All Rights Reserved. Python is distributed under the PSF License Agreement for Python, whose full text is at the address above.

## Compatibility with AGPL-3.0-or-later

These components keep their own licenses. The AGPL-3.0-or-later license of ZBookmarks is compatible with each one as used here:

- wxWindows Library Licence 3.1 (wxPython, wxWidgets): compatible. It is the GNU Library General Public Licence version 2 or later with an extra permission; that licence allows its code to be used under the GNU GPL version 3, and section 13 of the GNU GPL version 3 and of the GNU AGPL version 3 allows combining the two.
- PSF-2.0 (Python): compatible, as it is a permissive GPL-compatible license.
- Apache-2.0 (OpenSSL 3): compatible with GPL-3.0 and AGPL-3.0.
- PyInstaller bootloader (GPL-2.0-or-later with exception): compatible, and the exception allows any license for the packed program.
- Microsoft Visual C++ runtime: not covered by the GPL family but treated as a Windows system library that accompanies the executable. It is not part of the ZBookmarks source.
- Windows PowerShell and Windows itself: system components, not distributed with ZBookmarks.

No incompatibility was found for the components above.
