# ZBookmarks
# Copyright (C) 2026 ZAPPS SOFTWARE LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
ZBookmarks, built with wxPython.
Native Windows controls: NVDA, JAWS and Narrator read every field, checkbox
and button through MSAA and UI Automation. Tab order follows the reading
order; Enter and Space work on buttons; edit fields start focus mode.
"""

import sys, os, json, re, threading, subprocess, urllib.request, time, ctypes, traceback

import wx

# ─── Global error trap: turn silent failures into a visible, reportable dialog ─
def _on_unhandled_error(exc_type, exc, tb):
    try:
        msg = "".join(traceback.format_exception(exc_type, exc, tb))
        _log("UNHANDLED EXCEPTION:\n" + msg)
        if wx.GetApp() is None:
            wx.App(False)
        dlg = wx.MessageDialog(
            None, "Something went wrong:\n\n" + str(exc),
            "ZBookmarks — Unexpected error", wx.OK | wx.ICON_ERROR)
        dlg.SetExtendedMessage("The details are in the ZBookmarks log file.")
        dlg.ShowModal()
        dlg.Destroy()
    except Exception:
        traceback.print_exception(exc_type, exc, tb)

sys.excepthook = _on_unhandled_error

# ─── Resource helper (works both frozen .exe and dev script) ─────────────────
def _get_resource(filename):
    """Return absolute path to a bundled file, works for PyInstaller exe and dev."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


def _open_html(filename):
    """Open a bundled HTML file in the default browser."""
    try:
        os.startfile(_get_resource(filename))
    except Exception as e:
        _log(f"open page {filename}: error {e!r}")


# ─── Settings ────────────────────────────────────────────────────────────────
def _cfg_dir():
    r"""Return %AppData%\zbookmarks\, creating it if needed."""
    d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                     "zbookmarks")
    os.makedirs(d, exist_ok=True)
    return d

def _cfg_path():
    return os.path.join(_cfg_dir(), "zbookmarks_settings.json")

# ─── Log file — every grab step is recorded so failures are diagnosable ──────
_LOG_PATH = os.path.join(_cfg_dir(), "zbookmarks.log")

def _short(s, n=120):
    """Collapse whitespace and shorten a value for a log line."""
    s = str(s).replace("\r", " ").replace("\n", " ").strip()
    return s if len(s) <= n else s[:n] + "…"

def _log(msg):
    """Append one timestamped line to the log file (rotated at 256 KB)."""
    try:
        if os.path.exists(_LOG_PATH) and os.path.getsize(_LOG_PATH) > 262144:
            try:
                os.remove(_LOG_PATH)
            except Exception:
                pass
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg + "\n")
    except Exception:
        pass

DEFAULTS = {
    "auto_paste_url":      True,
    "auto_fetch_title":    True,
    "play_sound":          True,
    "close_on_success":    True,
    "desktop_shortcut":    False,
    "desktop_hotkey":      "",
    "save_dir":            "",
    "grab_active_url":     True,
}

def load_settings():
    try:
        if os.path.exists(_cfg_path()):
            with open(_cfg_path()) as f:
                s = json.load(f)
            for k, v in DEFAULTS.items():
                s.setdefault(k, v)
            return s
    except Exception:
        pass
    return dict(DEFAULTS)

def save_settings(s):
    try:
        with open(_cfg_path(), "w") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass

def _is_first_run():
    """True when no settings file exists yet — genuine first launch."""
    return not os.path.exists(_cfg_path())

# ─── Desktop folder helper (needed early for default save dir) ───────────────
def _desktop_folder():
    """Return the real Desktop folder, including OneDrive-redirected desktops."""
    buf = ctypes.create_unicode_buffer(320)
    # CSIDL_DESKTOP = 0
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf) == 0:
        return buf.value
    return os.path.join(os.path.expanduser("~"), "Desktop")

def default_save_dir():
    r"""Return (and create) Desktop\Bookmarks and Shortcuts."""
    d = os.path.join(_desktop_folder(), "Bookmarks and Shortcuts")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

# ─── Sound ────────────────────────────────────────────────────────────────────
def play_chime(wait=False):
    """Play the chime inside this program. No helper process: a helper started
    from the exe loads the exe's bundled DLLs and keeps them locked after the
    exe exits, so the exe cannot remove its temp folder. wait=True plays the
    short chime to the end, for when the window closes straight after."""
    wav = _get_resource("01.wav")
    if os.path.exists(wav):
        try:
            import winsound
            flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
            if not wait:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(wav, flags)
        except Exception:
            pass


# ─── Desktop shortcut creation ────────────────────────────────────────────────
def _hotkey_shortcut_path():
    return os.path.join(_desktop_folder(), "ZBookmarks.lnk")


def _shortcut_target():
    """Return (target, arguments, working_directory) for the desktop shortcut."""
    if getattr(sys, "frozen", False):
        exe = os.path.abspath(sys.executable)
        target, args, workdir = exe, "", os.path.dirname(exe)
    else:
        script = os.path.abspath(__file__)
        exe = sys.executable
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(pythonw):
            exe = pythonw
        target, args, workdir = exe, f'"{script}"', os.path.dirname(script)
    _log(f"shortcut target: target={target!r} args={args!r} workdir={workdir!r} frozen={getattr(sys, 'frozen', False)}")
    return target, args, workdir


def create_desktop_shortcut(hotkey=""):
    """Place a .lnk shortcut pointing at ZBookmarks.

    Works from both PyInstaller .exe and from a dev .py script.
    Logs every step so failures can be diagnosed.
    """
    dest = _hotkey_shortcut_path()
    hotkey = hotkey.strip().upper()
    _log(f"create_desktop_shortcut: dest={dest!r} hotkey={hotkey!r}")
    if hotkey and not _valid_hotkey(hotkey):
        _log("create_desktop_shortcut: invalid hotkey, aborting")
        return False

    target, args, workdir = _shortcut_target()

    env = os.environ.copy()
    env["SH_EXE"] = target
    env["SH_ARGS"] = args
    env["SH_WORKDIR"] = workdir
    env["SH_DEST"] = dest
    if hotkey:
        env["SH_HOTKEY"] = hotkey

    ps = (
        "$ws=New-Object -ComObject WScript.Shell;"
        "$sc=$ws.CreateShortcut($env:SH_DEST);"
        "$sc.TargetPath=$env:SH_EXE;"
        "$sc.Arguments=$env:SH_ARGS;"
        "$sc.WorkingDirectory=$env:SH_WORKDIR;"
        "$sc.Description='ZBookmarks — URL and folder shortcut creator';"
    )
    if hotkey:
        ps += "$sc.Hotkey=$env:SH_HOTKEY;"
    ps += "$sc.Save()"

    _log("create_desktop_shortcut: running PowerShell")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            env=env,
            capture_output=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        _log(f"create_desktop_shortcut: PS returncode={r.returncode} "
             f"stdout={r.stdout.decode(errors='replace')!r} "
             f"stderr={r.stderr.decode(errors='replace')!r}")
    except Exception as e:
        _log(f"create_desktop_shortcut: PS exception {e!r}")
        _log(traceback.format_exc())
        return False

    exists = os.path.exists(dest)
    _log(f"create_desktop_shortcut: shortcut exists after PS={exists}")

    if exists and hotkey:
        actual = get_desktop_shortcut_hotkey()
        _log(f"create_desktop_shortcut: readback hotkey={actual!r}")
        if actual.upper() != hotkey:
            _log("create_desktop_shortcut: WARNING hotkey readback mismatch — "
                 "the file is still created, but Windows may not have stored "
                 "the hotkey. Check the shortcut's Properties.")

    return exists


def remove_desktop_shortcut():
    """Remove the ZBookmarks desktop shortcut (user asked not to keep it)."""
    dest = _hotkey_shortcut_path()
    _log(f"remove_desktop_shortcut: dest={dest!r}")
    try:
        if os.path.exists(dest):
            os.remove(dest)
            _log("remove_desktop_shortcut: removed")
        return not os.path.exists(dest)
    except Exception as e:
        _log(f"remove_desktop_shortcut: error {e!r}")
        return False


def get_desktop_shortcut_hotkey():
    """Read the hotkey currently on the desktop shortcut ("" if none/absent)."""
    dest = _hotkey_shortcut_path()
    if not os.path.exists(dest):
        _log("get_desktop_shortcut_hotkey: no shortcut file")
        return ""
    _log(f"get_desktop_shortcut_hotkey: reading {dest!r}")
    ps = ("$ws=New-Object -ComObject WScript.Shell;"
          "$sc=$ws.CreateShortcut($env:SH_DEST);"
          "[Console]::Out.Write($sc.Hotkey)")
    env = os.environ.copy()
    env["SH_DEST"] = dest
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            env=env, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        txt = (r.stdout or "").strip()
        _log(f"get_desktop_shortcut_hotkey: output={txt!r}")
        return txt
    except Exception as e:
        _log(f"get_desktop_shortcut_hotkey: error {e!r}")
        return ""


def is_url(t):
    return t.strip().lower().startswith(('http://', 'https://', 'ftp://', 'ftps://'))

def is_dir_path(t):
    t = t.strip()
    return bool(re.match(r'^[a-zA-Z]:\\', t)) or t.startswith('\\\\')

def _valid_hotkey(h):
    """A Windows shortcut hotkey, e.g. Ctrl+Alt+F. Empty means 'none'."""
    h = h.strip()
    if not h:
        return True
    return bool(re.match(r'^([A-Za-z0-9]+\+)+[A-Za-z0-9]+$', h))

# ─── Clipboard (wx needs a running wx.App) ────────────────────────────────────
def clip_get():
    """Return the clipboard text, or "" (a few tries: another app may hold it)."""
    cb = wx.TheClipboard
    for _ in range(3):
        if cb.Open():
            try:
                data = wx.TextDataObject()
                if cb.IsSupported(wx.DataFormat(wx.DF_UNICODETEXT)) and cb.GetData(data):
                    return data.GetText() or ""
                return ""
            finally:
                cb.Close()
        time.sleep(0.03)
    return ""

def clip_set(text):
    cb = wx.TheClipboard
    for _ in range(3):
        if cb.Open():
            try:
                cb.SetData(wx.TextDataObject(text))
            finally:
                cb.Close()
            try:
                cb.Flush()   # keep it after ZBookmarks closes
            except Exception:
                pass
            return
        time.sleep(0.03)

# ─── Grab URL/path from the active window ─────────────────────────────────────
# Windows window classes whose address bar we can read (browsers + Explorer).
_ADDRESS_BAR_CLASSES = {
    "Chrome_WidgetWin_1",      # Chrome, Edge, Opera, Brave, Vivaldi
    "Chromium_WidgetWin_1",    # Chromium builds (e.g. Cromite)
    "MozillaWindowClass",      # Firefox
    "IEFrame",                 # Internet Explorer
    "CabinetWClass",           # File Explorer
    "ExploreWClass",           # older Explorer windows
    "ApplicationFrameWindow",  # UWP hosts (some Edge versions)
}


def _find_browser_hwnd():
    """Return the topmost visible browser/Explorer window, or 0."""
    user32 = ctypes.windll.user32
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if cls.value in _ADDRESS_BAR_CLASSES:
            found.append(hwnd)
            return False  # stop after first match
        return True
    user32.EnumWindows(_enum_proc, 0)
    return found[0] if found else 0


def _press_key(vk, mods=()):
    """Send one key press, with optional modifiers, to the focused window."""
    mod_vks = {"alt": 0x12, "ctrl": 0x11, "shift": 0x10}
    held = [mod_vks[m] for m in mods if m in mod_vks]
    user32 = ctypes.windll.user32
    for k in held:
        user32.keybd_event(k, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    for k in reversed(held):
        user32.keybd_event(k, 0, 2, 0)

def grab_active_url(hwnd=None):
    """Read the active browser/Explorer window's address bar.

    Returns the URL or folder path, or "" if nothing usable was found.
    Only touches windows we recognise, and only accepts results that
    look like a URL or a folder path. Every step is written to
    zbookmarks.log so a failure can be diagnosed.
    """
    try:
        user32 = ctypes.windll.user32
        if hwnd is None:
            hwnd = user32.GetForegroundWindow()
        if not hwnd:
            _log("grab: no foreground window found")
            return ""
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        cls_name = cls.value
        if cls_name not in _ADDRESS_BAR_CLASSES:
            _log(f"grab: active window class is '{cls_name}' — not a "
                 f"supported browser/Explorer window, skipped")
            return ""
        _log(f"grab: active window class '{cls_name}' — supported, trying "
             f"Alt+D / Ctrl+C")
        old = clip_get()
        _log("grab: clipboard before: " + _short(old or "(empty)"))
        text = ""
        for attempt in (1, 2, 3):
            # Focus the address bar (Alt+D), copy it (Ctrl+C),
            # close the dropdown (Esc)
            _press_key(0x44, ("alt",))
            time.sleep(0.15)
            _press_key(0x43, ("ctrl",))
            time.sleep(0.10)
            _press_key(0x1B)
            text = clip_get().strip()
            _log(f"grab: attempt {attempt} copied: " + _short(text or "(empty)"))
            if is_url(text) or is_dir_path(text):
                break
            time.sleep(0.15)
        if old and old != text:
            clip_set(old)              # put the user's clipboard back
        if is_url(text) or is_dir_path(text):
            _log("grab: accepted: " + _short(text))
            return text
        _log("grab: copied text is not a URL or folder path — ignored")
    except Exception as e:
        _log(f"grab: ERROR {e!r}")
        _log(traceback.format_exc())
    return ""

def create_url_shortcut(url, filepath):
    ps = ("$u=$env:HFM_URL;$f=$env:HFM_FILE;"
          "$c='[InternetShortcut]',('URL='+$u);"
          "$c|Out-File -FilePath $f -Encoding ascii")
    env = os.environ.copy()
    env["HFM_URL"]  = url
    env["HFM_FILE"] = filepath
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   env=env, capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    return os.path.exists(filepath)

def create_lnk_shortcut(target, filepath):
    ps = ("$t=$env:HFM_TARGET;$f=$env:HFM_FILE;"
          "$ws=New-Object -ComObject WScript.Shell;"
          "$sc=$ws.CreateShortcut($f);$sc.TargetPath=$t;$sc.Save()")
    env = os.environ.copy()
    env["HFM_TARGET"] = target
    env["HFM_FILE"]   = filepath
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   env=env, capture_output=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    return os.path.exists(filepath)

# ─── Title fetch ──────────────────────────────────────────────────────────────
class TitleFetcher:
    """Fetches a page title on a worker thread; the result comes back on the
    GUI thread through wx.CallAfter."""
    def __init__(self, on_done):
        self._on_done = on_done

    def fetch(self, url):
        threading.Thread(target=self._worker, args=(url,), daemon=True).start()

    def _worker(self, url):
        title = ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                raw = r.read(32768).decode("utf-8", errors="replace")
            m = re.search(r'<title[^>]*>(.*?)</title>', raw, re.I | re.S)
            if m:
                t = re.sub(r'\s+', ' ', m.group(1)).strip()
                title = re.sub(r'[\\/:*?"<>|]', '_', t)
        except Exception:
            pass
        try:
            wx.CallAfter(self._deliver, title)
        except Exception:
            pass

    def _deliver(self, title):
        try:
            self._on_done(title)
        except RuntimeError:
            pass   # the window was already closed

# ─── Colours and fonts (the same dark blue design as before) ─────────────────
C_WINDOW   = "#26344D"
C_PANEL    = "#33456B"
C_TEXT     = "#CFDCEE"
C_WHITE    = "#FFFFFF"
C_MUTED    = "#8FA9C9"
C_EDIT_BG  = "#1B2536"
C_EDIT_FG  = "#EDF2F9"
C_OK       = "#4CAF82"
C_WARN     = "#E0B45C"
C_ERROR    = "#E05C5C"

def _font(size, bold=False):
    info = wx.FontInfo(size).FaceName("Segoe UI")
    if bold:
        info = info.Bold()
    return wx.Font(info)

def _colour(widget, bg=None, fg=None):
    if bg:
        widget.SetBackgroundColour(wx.Colour(bg))
    if fg:
        widget.SetForegroundColour(wx.Colour(fg))
    return widget

# ─── Accessibility helper ─────────────────────────────────────────────────────
# A longer name or a description for one control, given to MSAA (and through
# it to UI Automation). Everything else comes from the native control itself.
if hasattr(wx, "Accessible"):
    class _Acc(wx.Accessible):
        def __init__(self, win, name="", desc=""):
            super().__init__(win)
            self.name = name
            self.desc = desc

        def GetName(self, childId):
            if childId == 0 and self.name:
                return (wx.ACC_OK, self.name)
            return (wx.ACC_NOT_IMPLEMENTED, "")

        def GetDescription(self, childId):
            if childId == 0 and self.desc:
                return (wx.ACC_OK, self.desc)
            return (wx.ACC_NOT_IMPLEMENTED, "")

        # Dark mode draws check boxes itself, and Windows then reports them as
        # plain buttons with no state. Report a check box and its state instead.
        def _check(self, childId):
            w = self.GetWindow()
            return w if childId == 0 and isinstance(w, wx.CheckBox) else None

        def GetRole(self, childId):
            if self._check(childId):
                return (wx.ACC_OK, wx.ROLE_SYSTEM_CHECKBUTTON)
            return (wx.ACC_NOT_IMPLEMENTED, 0)

        def GetState(self, childId):
            w = self._check(childId)
            if not w:
                return (wx.ACC_NOT_IMPLEMENTED, 0)
            st = wx.ACC_STATE_SYSTEM_FOCUSABLE
            if w.HasFocus():
                st |= wx.ACC_STATE_SYSTEM_FOCUSED
            if w.GetValue():
                st |= wx.ACC_STATE_SYSTEM_CHECKED
            if not w.IsEnabled():
                st |= wx.ACC_STATE_SYSTEM_UNAVAILABLE
            return (wx.ACC_OK, st)

        def GetDefaultAction(self, childId):
            w = self._check(childId)
            if not w:
                return (wx.ACC_NOT_IMPLEMENTED, "")
            return (wx.ACC_OK, "Uncheck" if w.GetValue() else "Check")

        def DoDefaultAction(self, childId):
            w = self._check(childId)
            if not w:
                return wx.ACC_NOT_IMPLEMENTED
            w.SetValue(not w.GetValue())
            evt = wx.CommandEvent(wx.wxEVT_CHECKBOX, w.GetId())
            evt.SetEventObject(w)
            evt.SetInt(int(w.GetValue()))
            w.GetEventHandler().ProcessEvent(evt)
            return wx.ACC_OK
else:
    _Acc = None

def _state_changed(win):
    """Tell screen readers a check box was checked or unchecked."""
    try:
        wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_STATECHANGE, win,
                                  wx.OBJID_CLIENT, wx.ACC_SELF)
    except Exception:
        pass

# ─── Real check box type for dark-mode check boxes ───────────────────────────
# In dark mode wx draws check boxes itself, so Windows marks them as self-drawn
# buttons, and some screen readers (JAWS) then read "button" with no state on
# focus. Between messages the control is marked as a check box; while it handles
# a message it is self-drawn again, so wx draws and behaves exactly as before.
# BM_GETCHECK and BM_GETSTATE answer with the wx value.
import ctypes.wintypes as _wt
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, _wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM)
_u32.GetWindowLongW.argtypes = [_wt.HWND, ctypes.c_int]
_u32.GetWindowLongW.restype = ctypes.c_long
_u32.SetWindowLongW.argtypes = [_wt.HWND, ctypes.c_int, ctypes.c_long]
_u32.SetWindowLongW.restype = ctypes.c_long
_GetWndPtr = getattr(_u32, "GetWindowLongPtrW", _u32.GetWindowLongW)
_SetWndPtr = getattr(_u32, "SetWindowLongPtrW", _u32.SetWindowLongW)
_GetWndPtr.argtypes = [_wt.HWND, ctypes.c_int]
_GetWndPtr.restype = ctypes.c_void_p
_SetWndPtr.argtypes = [_wt.HWND, ctypes.c_int, ctypes.c_void_p]
_SetWndPtr.restype = ctypes.c_void_p
_u32.CallWindowProcW.argtypes = [ctypes.c_void_p, _wt.HWND, _wt.UINT, _wt.WPARAM, _wt.LPARAM]
_u32.CallWindowProcW.restype = _LRESULT
_u32.InvalidateRect.argtypes = [_wt.HWND, ctypes.c_void_p, _wt.BOOL]

_GWL_STYLE, _GWLP_WNDPROC = -16, -4
_BS_TYPEMASK, _BS_AUTOCHECKBOX, _BS_OWNERDRAW = 0xF, 0x3, 0xB
_WM_STYLECHANGING, _WM_STYLECHANGED, _WM_NCDESTROY = 0x7C, 0x7D, 0x82
_BM_GETCHECK, _BM_SETCHECK, _BM_GETSTATE = 0xF0, 0xF1, 0xF2

def _native_check_type(c):
    """Mark a self-drawn wx.CheckBox as a real check box for Windows.
    Does nothing when wx draws the control natively."""
    try:
        hwnd = c.GetHandle()
        if (_u32.GetWindowLongW(hwnd, _GWL_STYLE) & _BS_TYPEMASK) != _BS_OWNERDRAW:
            return
        st = {"depth": 0, "flipping": False, "gone": False}
        prev = _GetWndPtr(hwnd, _GWLP_WNDPROC)

        def set_type(t):
            s = _u32.GetWindowLongW(hwnd, _GWL_STYLE)
            if (s & _BS_TYPEMASK) != t:
                st["flipping"] = True
                try:
                    _u32.SetWindowLongW(hwnd, _GWL_STYLE, (s & ~_BS_TYPEMASK) | t)
                finally:
                    st["flipping"] = False

        def proc(h, msg, wp, lp):
            if st["flipping"] and msg in (_WM_STYLECHANGING, _WM_STYLECHANGED):
                return 0
            st["depth"] += 1
            if st["depth"] == 1:
                set_type(_BS_OWNERDRAW)
            try:
                if msg == _BM_GETCHECK:
                    return 1 if c.GetValue() else 0
                r = _u32.CallWindowProcW(prev, h, msg, wp, lp)
                if msg == _BM_GETSTATE:
                    r = (r & ~3) | (1 if c.GetValue() else 0)
                elif msg == _BM_SETCHECK:
                    _u32.InvalidateRect(h, None, True)
                elif msg == _WM_NCDESTROY:
                    st["gone"] = True
                    if _GetWndPtr(h, _GWLP_WNDPROC) == ctypes.cast(cb, ctypes.c_void_p).value:
                        _SetWndPtr(h, _GWLP_WNDPROC, prev)
                return r
            finally:
                st["depth"] -= 1
                if st["depth"] == 0 and not st["gone"]:
                    set_type(_BS_AUTOCHECKBOX)

        cb = _WNDPROC(proc)
        c._zb_native_check = cb      # keeps the callback alive with the control
        _SetWndPtr(hwnd, _GWLP_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
        set_type(_BS_AUTOCHECKBOX)
    except Exception as e:
        _log(f"check box type: {e!r}")

def _acc(win, name="", desc=""):
    """Give a control a screen reader name and/or description."""
    if _Acc is None:
        return None
    try:
        a = _Acc(win, name, desc)
        win.SetAccessible(a)
        win._zb_acc = a
        return a
    except Exception as e:
        _log(f"accessible name for {name or desc!r}: {e!r}")
        return None

def _set_desc(win, desc):
    a = getattr(win, "_zb_acc", None)
    if a is not None:
        a.desc = desc
    else:
        _acc(win, desc=desc)

# ─── Widget helpers ───────────────────────────────────────────────────────────
def btn(parent, label, callback, name="", min_width=None):
    b = wx.Button(parent, label=label)
    b.SetFont(_font(10, bold=True))
    b.Bind(wx.EVT_BUTTON, lambda evt: callback())
    if min_width:
        b.SetMinSize((min_width, -1))
    if name and name != label:
        _acc(b, name)
    return b

def label(parent, text, fg=C_TEXT, size=10, bold=False, wrap=0):
    l = wx.StaticText(parent, label=text)
    l.SetFont(_font(size, bold))
    l.SetForegroundColour(wx.Colour(fg))
    if wrap:
        l.Wrap(wrap)
    return l

def edit(parent, value="", hint="", enter=False):
    """A single-line field. enter=True: Enter is handled by the window
    (main window); otherwise Enter presses the dialog's default button."""
    e = wx.TextCtrl(parent, value=value, style=wx.TE_PROCESS_ENTER if enter else 0)
    e.SetFont(_font(11))
    _colour(e, C_EDIT_BG, C_EDIT_FG)
    if hint:
        e.SetHint(hint)
    return e

def checkbox(parent, text, checked, name="", desc=""):
    c = wx.CheckBox(parent, label=text)
    c.SetFont(_font(10))
    c.SetValue(bool(checked))
    _acc(c, name if name != text else "", desc)
    _native_check_type(c)
    def _changed(evt):
        _state_changed(c)
        evt.Skip()
    c.Bind(wx.EVT_CHECKBOX, _changed)
    return c

def sep(parent):
    return wx.StaticLine(parent)

def section(parent, title):
    """A titled group (screen readers announce its title on entering it).
    Returns (box, sizer): put the controls in the box, add them to the sizer."""
    sb = wx.StaticBoxSizer(wx.VERTICAL, parent, title)
    box = sb.GetStaticBox()
    box.SetFont(_font(11, bold=True))
    _colour(box, C_PANEL)
    return box, sb

def _escape_closes(dialog, result):
    def on_key(evt):
        if evt.GetKeyCode() == wx.WXK_ESCAPE:
            dialog.EndModal(result)
        else:
            evt.Skip()
    dialog.Bind(wx.EVT_CHAR_HOOK, on_key)

def _activate(win):
    """Bring a top-level window to the front and give it the keyboard."""
    try:
        if not win:
            return
        win.Raise()
        ctypes.windll.user32.SetForegroundWindow(win.GetHandle())
    except Exception:
        pass

def _app_icon():
    no_log = wx.LogNull()   # a missing icon must not pop up an error box
    try:
        if getattr(sys, "frozen", False):
            ic = wx.Icon(wx.IconLocation(sys.executable, 0))
        else:
            path = _get_resource("icon.ico")
            if not os.path.exists(path):
                return None
            ic = wx.Icon(path, wx.BITMAP_TYPE_ICO)
        return ic if ic.IsOk() else None
    except Exception:
        return None
    finally:
        del no_log


# ─── More dialog — pure button menu, opens browser pages ─────────────────────
class MoreDialog(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="More — ZBookmarks")
        _colour(self, C_WINDOW)
        root = wx.BoxSizer(wx.VERTICAL)

        root.Add(label(self, "More", C_WHITE, 14, True), 0, wx.BOTTOM, 4)
        root.Add(sep(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)

        self.about_btn = btn(self, "About ZBookmarks",
                             lambda: _open_html("about.html"),
                             "About ZBookmarks, opens in your default browser")
        tips_btn = btn(self, "Tips and Tricks",
                       lambda: _open_html("tips.html"),
                       "Tips and Tricks, opens in your default browser")
        privacy_btn = btn(self, "Privacy Policy and Copyrights",
                          lambda: _open_html("privacy.html"),
                          "Privacy Policy and Copyrights, opens in your default browser")
        for b in (self.about_btn, tips_btn, privacy_btn):
            root.Add(b, 0, wx.EXPAND | wx.TOP, 5)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        close_btn = btn(self, "Close", lambda: self.EndModal(wx.ID_OK),
                        "Close More dialog")
        row.Add(close_btn)
        root.Add(row, 0, wx.EXPAND | wx.TOP, 15)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(root, 1, wx.EXPAND | wx.ALL, 20)
        self.SetSizer(outer)
        self.SetMinSize((520, -1))
        self.Fit()
        self.CentreOnParent()
        _escape_closes(self, wx.ID_OK)
        self.about_btn.SetFocus()


# ─── Replace confirmation — never silently overwrite a shortcut ──────────────
class ConfirmReplaceDialog(wx.Dialog):
    """Asked before replacing an existing shortcut file."""
    def __init__(self, filepath, parent=None):
        super().__init__(parent, title="Replace Existing File?")
        _colour(self, C_WINDOW)
        self._replace = False
        root = wx.BoxSizer(wx.VERTICAL)

        root.Add(label(self, "File already exists", C_WHITE, 14, True), 0, wx.BOTTOM, 8)
        text = (f"A shortcut named “{os.path.basename(filepath)}” already exists "
                f"in {os.path.dirname(filepath)}.\n"
                "Replace it with the new one?")
        root.Add(label(self, text, C_TEXT, 10, wrap=460), 0, wx.BOTTOM, 16)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        self.cancel_btn = btn(self, "Cancel", self._cancel,
                              "Cancel, keep the existing file")
        replace_btn = btn(self, "Replace", self._replace_yes,
                          "Replace the existing file")
        row.Add(self.cancel_btn, 0, wx.RIGHT, 8)
        row.Add(replace_btn)
        root.Add(row, 0, wx.EXPAND)
        # The question is also the Cancel button's description, so it is
        # read where focus lands.
        _set_desc(self.cancel_btn,
                  f"Replace {os.path.basename(filepath)} in "
                  f"{os.path.dirname(filepath)} or keep the existing file?")

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(root, 1, wx.EXPAND | wx.ALL, 20)
        self.SetSizer(outer)
        self.SetMinSize((500, -1))
        self.Fit()
        self.CentreOnParent()
        self.cancel_btn.SetDefault()
        _escape_closes(self, wx.ID_CANCEL)
        self.cancel_btn.SetFocus()

    def _cancel(self):
        self._replace = False
        self.EndModal(wx.ID_CANCEL)

    def _replace_yes(self):
        self._replace = True
        self.EndModal(wx.ID_OK)

    @property
    def replace(self):
        return self._replace


# ─── Settings dialog ──────────────────────────────────────────────────────────
class SettingsDialog(wx.Dialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent, title="Settings — ZBookmarks")
        _colour(self, C_WINDOW)
        self.settings = settings
        self._build()

    def _build(self):
        root = wx.BoxSizer(wx.VERTICAL)

        root.Add(label(self, "Settings", C_WHITE, 14, True), 0, wx.BOTTOM, 4)
        root.Add(sep(self), 0, wx.EXPAND | wx.BOTTOM, 8)

        # ── General options ──
        panel = _colour(wx.Panel(self), C_PANEL)
        pv = wx.BoxSizer(wx.VERTICAL)
        self.cb_paste = checkbox(panel, "Auto-detect and paste URL from clipboard on launch",
                                 self.settings["auto_paste_url"])
        self.cb_title = checkbox(panel, "Auto-fetch webpage title into Shortcut Name field",
                                 self.settings["auto_fetch_title"])
        self.cb_sound = checkbox(panel, "Play success chime sound when file is created",
                                 self.settings["play_sound"])
        self.cb_close = checkbox(panel, "Close app after successfully creating a shortcut",
                                 self.settings["close_on_success"],
                                 desc="App stays open if shortcut creation fails.")
        self.cb_grab = checkbox(panel, "Grab URL/path from the active window when opened",
                                self.settings.get("grab_active_url", False),
                                name="Grab URL or folder path from the active window when opened",
                                desc="Reads the address bar of the focused browser or File "
                                     "Explorer window, for example after pressing the global hotkey.")
        for c in (self.cb_paste, self.cb_title, self.cb_sound, self.cb_close, self.cb_grab):
            pv.Add(c, 0, wx.TOP | wx.BOTTOM, 4)
        pw = wx.BoxSizer(wx.VERTICAL)
        pw.Add(pv, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 10)
        panel.SetSizer(pw)
        root.Add(panel, 0, wx.EXPAND | wx.BOTTOM, 8)

        # ── Desktop shortcut & global hotkey ──
        hk_box, hv = section(self, "Desktop shortcut and global hotkey")
        has_desktop = os.path.exists(_hotkey_shortcut_path())
        # Reflect reality: checked if the shortcut exists or was enabled before
        self.cb_desktop = checkbox(hk_box, "Create a ZBookmarks shortcut on the Desktop",
                                   has_desktop or self.settings.get("desktop_shortcut", False))
        self.cb_desktop.Bind(wx.EVT_CHECKBOX,
                             lambda evt: (self._on_desktop_toggled(evt.IsChecked()), evt.Skip()))
        hv.Add(self.cb_desktop, 0, wx.ALL, 6)

        hk_row = wx.BoxSizer(wx.HORIZONTAL)
        hk_row.Add(label(hk_box, "Global hotkey:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        # Prefill: stored setting first, otherwise the hotkey currently on the shortcut
        stored = self.settings.get("desktop_hotkey", "")
        current = get_desktop_shortcut_hotkey()
        self.hotkey_edit = edit(hk_box, stored or current or "",
                                "Ctrl+Alt+F — leave empty for none")
        self._hotkey_desc = ("A hotkey you can press anywhere in Windows to open "
                             "ZBookmarks. For example Ctrl+Alt+F. Leave empty for no "
                             "hotkey. It is stored on the desktop shortcut itself, so it "
                             "only works while that shortcut exists.")
        _acc(self.hotkey_edit, "Global hotkey for the desktop shortcut", self._hotkey_desc)
        hk_row.Add(self.hotkey_edit, 1)
        hv.Add(hk_row, 0, wx.EXPAND | wx.ALL, 6)

        hv.Add(label(hk_box,
                     "Pressing the hotkey anywhere in Windows opens ZBookmarks. "
                     "It is stored on the desktop shortcut itself, so it only works "
                     "while that shortcut exists.", C_TEXT, 10, wrap=460),
               0, wx.ALL, 6)
        self.settings_msg = label(hk_box, "", C_TEXT, 9)
        hv.Add(self.settings_msg, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        root.Add(hv, 0, wx.EXPAND | wx.BOTTOM, 8)

        # ── Save location ──
        dir_box, dv = section(self, "Save location")
        dir_row = wx.BoxSizer(wx.HORIZONTAL)
        dir_row.Add(label(dir_box, "Folder:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.dir_edit = edit(dir_box,
                             (self.settings.get("save_dir") or "").strip() or default_save_dir(),
                             "C:\\Users\\You\\Desktop\\Bookmarks and Shortcuts")
        self._dir_desc = ("Where new shortcut files are saved. You can type a folder "
                          "path or use the Browse button. By default ZBookmarks saves "
                          "new shortcuts in the Bookmarks and Shortcuts folder on your "
                          "Desktop.")
        _acc(self.dir_edit, "Save folder for new shortcuts", self._dir_desc)
        dir_row.Add(self.dir_edit, 1, wx.RIGHT, 8)
        browse_btn = btn(dir_box, "Browse…", self._browse_dir,
                         "Browse for save folder", min_width=90)
        dir_row.Add(browse_btn)
        dv.Add(dir_row, 0, wx.EXPAND | wx.ALL, 6)
        dv.Add(label(dir_box,
                     "By default ZBookmarks saves new shortcuts in the "
                     "Bookmarks and Shortcuts folder on your Desktop. "
                     "Change it to any folder you like.", C_TEXT, 10, wrap=460),
               0, wx.ALL, 6)
        root.Add(dv, 0, wx.EXPAND | wx.BOTTOM, 8)

        log_row = wx.BoxSizer(wx.HORIZONTAL)
        log_row.AddStretchSpacer()
        log_btn = btn(self, "Open log file", self._open_log,
                      "Open the ZBookmarks log file used to diagnose the URL grab")
        log_btn.SetFont(_font(10))
        log_row.Add(log_btn)
        root.Add(log_row, 0, wx.EXPAND | wx.BOTTOM, 8)

        row = wx.BoxSizer(wx.HORIZONTAL)
        more_btn = btn(self, "More", self._open_more)
        save_btn = btn(self, "Save and Close", self._save)
        row.Add(more_btn)
        row.AddStretchSpacer()
        row.Add(save_btn)
        root.Add(row, 0, wx.EXPAND)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(root, 1, wx.EXPAND | wx.ALL, 14)
        self.SetSizer(outer)
        self.SetMinSize((520, -1))
        self.Fit()
        self.CentreOnParent()
        save_btn.SetDefault()
        _escape_closes(self, wx.ID_CANCEL)

        self._on_desktop_toggled(self.cb_desktop.GetValue())
        self.cb_paste.SetFocus()

    def _on_desktop_toggled(self, checked):
        self.hotkey_edit.Enable(bool(checked))

    def _browse_dir(self):
        start = self.dir_edit.GetValue().strip() or default_save_dir()
        dlg = wx.DirDialog(self, "Choose a folder to save shortcuts", start,
                           wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.dir_edit.SetValue(dlg.GetPath())
        finally:
            dlg.Destroy()
        self.dir_edit.SetFocus()

    def _show_settings_msg(self, msg, color, field=None, field_desc=""):
        """Show a problem under the hotkey field. The message is also read
        where focus goes: the field it is about gets it as its description."""
        self.settings_msg.SetLabel(msg)
        self.settings_msg.SetForegroundColour(wx.Colour(color))
        self.settings_msg.Wrap(460)
        self.Layout()
        self.Fit()
        if field is not None:
            _set_desc(field, msg + " " + field_desc)
            field.SetFocus()

    def _save(self):
        self.settings["auto_paste_url"]   = self.cb_paste.GetValue()
        self.settings["auto_fetch_title"] = self.cb_title.GetValue()
        self.settings["play_sound"]       = self.cb_sound.GetValue()
        self.settings["close_on_success"] = self.cb_close.GetValue()

        want_desktop = self.cb_desktop.GetValue()
        hk = self.hotkey_edit.GetValue().strip()
        _log(f"settings save: want_desktop={want_desktop} hk={hk!r}")

        if want_desktop:
            if not _valid_hotkey(hk):
                _log("settings save: invalid hotkey")
                self._show_settings_msg(
                    "Invalid hotkey. Use a combination like Ctrl+Alt+F "
                    "(letters, numbers and + only), or leave it empty for none.",
                    C_ERROR, self.hotkey_edit, self._hotkey_desc)
                return
            try:
                ok = create_desktop_shortcut(hk)
            except Exception as e:
                _log("settings save: create_desktop_shortcut exception " + repr(e))
                _log(traceback.format_exc())
                self._show_settings_msg(
                    "Could not create the desktop shortcut due to an error. "
                    "See the log file for details.",
                    C_ERROR, self.hotkey_edit, self._hotkey_desc)
                return
            _log(f"settings save: create_desktop_shortcut returned {ok}")
            if not ok:
                self._show_settings_msg(
                    "Could not create the desktop shortcut. Nothing was saved — "
                    "please check the hotkey and try again.",
                    C_ERROR, self.hotkey_edit, self._hotkey_desc)
                return
        else:
            if os.path.exists(_hotkey_shortcut_path()):
                remove_desktop_shortcut()

        savedir = self.dir_edit.GetValue().strip()
        if savedir:
            try:
                os.makedirs(savedir, exist_ok=True)
            except Exception:
                self._show_settings_msg(
                    "Could not use that folder. Check the path and try again.",
                    C_ERROR, self.dir_edit, self._dir_desc)
                return
        self.settings["desktop_shortcut"] = want_desktop
        self.settings["desktop_hotkey"]   = hk if want_desktop else ""
        self.settings["save_dir"]         = savedir
        self.settings["grab_active_url"]  = self.cb_grab.GetValue()
        _log("settings save: writing settings")
        save_settings(self.settings)
        _log("settings save: accepted")
        self.EndModal(wx.ID_OK)

    def _open_log(self):
        try:
            if os.path.exists(_LOG_PATH):
                os.startfile(_LOG_PATH)
        except Exception:
            pass

    def _open_more(self):
        dlg = MoreDialog(self)
        dlg.ShowModal()
        dlg.Destroy()


# ─── First-run dialog ────────────────────────────────────────────────────────
class FirstRunDialog(wx.Dialog):
    """
    Shown once, on first launch only (no settings file found).
    Lets the user opt into a desktop shortcut and an optional global hotkey.
    """
    def __init__(self, parent=None):
        super().__init__(parent, title="Welcome to ZBookmarks")
        _colour(self, C_WINDOW)
        self._build()

    def _build(self):
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(label(self, "Welcome to ZBookmarks", C_WHITE, 14, True), 0, wx.BOTTOM, 6)
        root.Add(label(self, "First-time setup. Choose the optional conveniences below, "
                             "then press Continue.", C_TEXT, 10, wrap=470), 0, wx.BOTTOM, 8)
        root.Add(sep(self), 0, wx.EXPAND | wx.BOTTOM, 10)

        panel = _colour(wx.Panel(self), C_PANEL)
        pv = wx.BoxSizer(wx.VERTICAL)
        self.cb_desktop = checkbox(panel, "Create a shortcut to ZBookmarks on the Desktop", True)
        self.cb_desktop.Bind(wx.EVT_CHECKBOX,
                             lambda evt: (self._on_desktop_toggled(evt.IsChecked()), evt.Skip()))
        pv.Add(self.cb_desktop, 0, wx.BOTTOM, 8)

        self.cb_grab = checkbox(panel, "Grab the URL or folder path from the active window when opened",
                                True,
                                desc="For example, press the global hotkey while a web page or a "
                                     "folder is open and ZBookmarks fills it in automatically.")
        pv.Add(self.cb_grab, 0, wx.BOTTOM, 8)

        self.hotkey_edit = edit(panel, "Ctrl+Alt+F", "Ctrl+Alt+F — leave empty for none")
        self._hotkey_desc = ("A hotkey you can press anywhere in Windows to open ZBookmarks. "
                             "For example Ctrl+Alt+F. Leave empty for no hotkey. You can "
                             "change it later in Settings.")
        _acc(self.hotkey_edit, "Global hotkey for the desktop shortcut", self._hotkey_desc)
        pv.Add(self.hotkey_edit, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.hotkey_note = label(panel,
                                 "The hotkey is stored on the desktop shortcut itself (Windows "
                                 "Shortcut key), so it opens ZBookmarks from anywhere. "
                                 "You can change it later in Settings.", C_TEXT, 10, wrap=440)
        pv.Add(self.hotkey_note, 0, wx.BOTTOM, 8)

        self.err_lbl = label(panel, "", C_ERROR, 9)
        pv.Add(self.err_lbl, 0, wx.EXPAND)

        pw = wx.BoxSizer(wx.VERTICAL)
        pw.Add(pv, 1, wx.EXPAND | wx.ALL, 14)
        panel.SetSizer(pw)
        root.Add(panel, 0, wx.EXPAND | wx.BOTTOM, 12)

        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        cont_btn = btn(self, "Continue", self._continue,
                       "Continue, apply selections and open ZBookmarks", min_width=120)
        row.Add(cont_btn)
        root.Add(row, 0, wx.EXPAND)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(root, 1, wx.EXPAND | wx.ALL, 20)
        self.SetSizer(outer)
        self.SetMinSize((520, 430))
        self.Fit()
        self.CentreOnParent()
        cont_btn.SetDefault()
        # Escape continues with the current choices, as before
        _escape_closes(self, wx.ID_OK)
        self._on_desktop_toggled(self.cb_desktop.GetValue())
        self.cb_desktop.SetFocus()

    def _on_desktop_toggled(self, checked):
        self.hotkey_edit.Enable(bool(checked))
        self.hotkey_note.Enable(bool(checked))
        if not checked:
            self.err_lbl.SetLabel("")

    def _continue(self):
        if self.cb_desktop.GetValue():
            hk = self.hotkey_edit.GetValue().strip()
            if not _valid_hotkey(hk):
                msg = ("Invalid hotkey. Use a combination like Ctrl+Alt+F "
                       "(letters, numbers and + only), or leave it empty for none.")
                self.err_lbl.SetLabel(msg)
                self.err_lbl.Wrap(440)
                self.Layout()
                _set_desc(self.hotkey_edit, msg + " " + self._hotkey_desc)
                self.hotkey_edit.SetFocus()
                return
        self.EndModal(wx.ID_OK)

    @property
    def wants_desktop(self):
        return self.cb_desktop.GetValue()

    @property
    def hotkey(self):
        return self.hotkey_edit.GetValue().strip()

    @property
    def wants_grab(self):
        return self.cb_grab.GetValue()


# ─── Main window ─────────────────────────────────────────────────────────────
class MainWindow(wx.Frame):
    def __init__(self, grabbed_url="", source_hwnd=0):
        super().__init__(None, title="ZBookmarks", size=(600, 460))
        self._first_run  = _is_first_run()
        self._grabbed    = grabbed_url or ""
        self._source_hwnd = source_hwnd or 0
        self.settings    = load_settings()
        self._fetch_busy = False
        self._fetcher    = TitleFetcher(self._on_title_fetched)

        ic = _app_icon()
        if ic:
            self.SetIcon(ic)
        self.SetMinSize((560, 420))

        root = _colour(wx.Panel(self), C_WINDOW)
        self.root = root
        self.panel = panel = _colour(wx.Panel(root), C_PANEL)
        pv = wx.BoxSizer(wx.VERTICAL)

        # Each label is created right before its field, so screen readers
        # use it as the field's name.
        pv.Add(label(panel, "path"), 0, wx.BOTTOM, 4)
        url_row = wx.BoxSizer(wx.HORIZONTAL)
        self.url_edit = edit(panel, enter=True)
        self.url_edit.Bind(wx.EVT_TEXT, lambda evt: self._on_url_changed(self.url_edit.GetValue()))
        self.url_edit.Bind(wx.EVT_TEXT_ENTER, lambda evt: self._generate())
        url_row.Add(self.url_edit, 1, wx.RIGHT, 8)
        self.paste_btn = btn(panel, "Paste", self._paste_clipboard,
                             "Paste URL from clipboard", min_width=80)
        url_row.Add(self.paste_btn)
        pv.Add(url_row, 0, wx.EXPAND | wx.BOTTOM, 8)

        pv.Add(label(panel, "name"), 0, wx.BOTTOM, 4)
        self.name_edit = edit(panel, enter=True)
        self.name_edit.Bind(wx.EVT_TEXT_ENTER, lambda evt: self._generate())
        pv.Add(self.name_edit, 0, wx.EXPAND | wx.BOTTOM, 8)

        self.status_lbl = label(panel, "", C_TEXT, 9)
        pv.Add(self.status_lbl, 0, wx.EXPAND | wx.BOTTOM, 8)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.gen_btn = btn(panel, "Generate", self._generate)
        self.set_btn = btn(panel, "Settings", self._open_settings,
                           "Open Settings", min_width=110)
        btn_row.Add(self.gen_btn, 1, wx.RIGHT, 8)
        btn_row.Add(self.set_btn)
        pv.Add(btn_row, 0, wx.EXPAND)

        pw = wx.BoxSizer(wx.VERTICAL)
        pw.Add(pv, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 16)
        pw.InsertSpacer(0, 14)
        pw.AddSpacer(14)
        panel.SetSizer(pw)

        # ── Footer — always shows where shortcuts are saved ──
        self.footer_lbl = label(root, f"Saves to: {self._resolve_save_dir()}", C_MUTED, 8)

        bwl = wx.BoxSizer(wx.VERTICAL)
        bwl.Add(panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        bwl.AddStretchSpacer(1)
        bwl.Add(self.footer_lbl, 0, wx.EXPAND | wx.ALL, 12)
        root.SetSizer(bwl)
        self.Bind(wx.EVT_SIZE, self._on_size)

        if self._grabbed:
            self.url_edit.SetValue(self._grabbed)
            self.url_edit.SetInsertionPointEnd()

        if self.settings["auto_paste_url"]:
            wx.CallLater(200, self._auto_paste)

        self.url_edit.SetFocus()

        # Show first-run dialog after the window is painted
        if self._first_run:
            wx.CallLater(100, self._do_first_run)
        else:
            # If the pre-show grab found nothing (e.g. a console window was
            # the active one), try once more after we are visible: briefly
            # hand focus back to the window the user was in, then retake it.
            if (not self._grabbed
                    and self.settings.get("grab_active_url", False)):
                wx.CallLater(180, self._fallback_grab)

    def _on_size(self, evt):
        evt.Skip()
        wx.CallAfter(self._rewrap)

    def _rewrap(self):
        if not self:
            return
        w = max(200, self.panel.GetClientSize().width - 32)
        self.status_lbl.Wrap(w)
        self.footer_lbl.Wrap(max(200, self.root.GetClientSize().width - 24))
        self.root.Layout()

    # ── First-run setup ───────────────────────────────────────────────────────
    def _do_first_run(self):
        # Save defaults first so the file exists (marks first-run as done)
        save_settings(self.settings)

        dlg = FirstRunDialog(self)
        dlg.ShowModal()

        self.settings["grab_active_url"] = dlg.wants_grab
        if dlg.wants_desktop:
            ok = create_desktop_shortcut(dlg.hotkey)
            self.settings["desktop_shortcut"] = True
            self.settings["desktop_hotkey"]   = dlg.hotkey
            if not ok:
                _log("first-run: desktop shortcut creation failed")
        dlg.Destroy()
        save_settings(self.settings)
        _log("first-run saved: grab_active_url="
             + str(self.settings.get("grab_active_url")))
        self.url_edit.SetFocus()

    def _retake_focus(self):
        _activate(self)
        self.url_edit.SetFocus()

    def _fallback_grab(self):
        """Retry the grab after the window is shown."""
        if not self or self.url_edit.GetValue().strip():
            return
        if self.settings.get("grab_active_url", False) is False:
            return
        hwnd = self._source_hwnd
        # If the saved window isn't a usable browser/Explorer, find one now
        if hwnd:
            try:
                user32 = ctypes.windll.user32
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                if cls.value not in _ADDRESS_BAR_CLASSES:
                    hwnd = 0
            except Exception:
                hwnd = 0
        if not hwnd:
            hwnd = _find_browser_hwnd()
        if not hwnd:
            self._status(
                "Could not grab from the active window. Make the browser or "
                "folder the focused window, then press the global hotkey.",
                C_WARN)
            return
        try:
            user32 = ctypes.windll.user32
            # Bring the target to the front
            got_focus = False
            for _ in range(5):
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.08)
                if user32.GetForegroundWindow() == hwnd:
                    got_focus = True
                    break
            if not got_focus:
                _log("grab fallback: could not bring the target window to "
                     "the front — skipped")
                self._retake_focus()
                return
            text = grab_active_url(hwnd)
            # Retake focus: our own window is allowed to grab it back.
            self._retake_focus()
            if text:
                self.url_edit.SetValue(text)
                self.url_edit.SetInsertionPointEnd()
            else:
                self._status(
                    "Could not grab from the active window. Make the browser "
                    "or folder the focused window, then press the global hotkey.",
                    C_WARN)
        except Exception as e:
            _log(f"grab fallback error: {e!r}")
            try:
                self._retake_focus()
            except Exception:
                pass

    def _auto_paste(self):
        if not self or self.url_edit.GetValue().strip():
            return  # already filled (e.g. grabbed from the active window)
        text = clip_get().strip()
        if text and (is_url(text) or is_dir_path(text)):
            self.url_edit.SetValue(text)
            self.url_edit.SetInsertionPointEnd()

    def _paste_clipboard(self):
        text = clip_get().strip()
        if text:
            self.url_edit.SetValue(text)
            self.url_edit.SetInsertionPointEnd()
            self._status("Pasted from clipboard.", C_TEXT)
        else:
            self._status("Clipboard is empty.", C_ERROR)

    def _resolve_save_dir(self):
        d = (self.settings.get("save_dir") or "").strip()
        if d:
            return d
        return default_save_dir()

    def _on_url_changed(self, text):
        if not self.settings["auto_fetch_title"]:
            return
        if is_url(text) and not self._fetch_busy:
            self._fetch_busy = True
            self._status("Fetching page title…", C_TEXT)
            self._fetcher.fetch(text)

    def _on_title_fetched(self, title):
        if not self:
            return
        self._fetch_busy = False
        if title:
            if not self.name_edit.GetValue().strip():
                self.name_edit.SetValue(title)
                self._status(f"Title fetched: {title[:60]}", C_OK)
            else:
                self._status("Title fetched (name field already filled).", C_TEXT)
        else:
            self._status("Could not fetch title — enter name manually.", C_WARN)

    def _generate(self):
        target = self.url_edit.GetValue().strip()
        name   = self.name_edit.GetValue().strip() or "New Shortcut"

        if not target:
            self._status("Please enter a URL or directory path first.", C_ERROR)
            self.url_edit.SetFocus()
            return

        safe = re.sub(r'[\\/:*?"<>|]', '_', name)
        save_dir = self._resolve_save_dir()

        if is_dir_path(target):
            filepath = os.path.join(save_dir, safe + ".lnk")
        else:
            filepath = os.path.join(save_dir, safe + ".url")

        # Never silently overwrite an existing shortcut
        if os.path.exists(filepath):
            dlg = ConfirmReplaceDialog(filepath, self)
            dlg.ShowModal()
            replace = dlg.replace
            dlg.Destroy()
            if not replace:
                self._status("Cancelled — existing file was not replaced.", C_WARN)
                return

        if is_dir_path(target):
            ok = create_lnk_shortcut(target, filepath)
        else:
            ok = create_url_shortcut(target, filepath)

        if ok:
            # Persistent feedback — the status line tells the user the full path
            self._status(f"Shortcut created: {filepath}", C_OK)
            if self.settings["play_sound"]:
                play_chime(wait=self.settings.get("close_on_success", False))
            if self.settings.get("close_on_success", False):
                self.Close()
        else:
            self._status(
                "Failed to create file. Check for invalid characters.", C_ERROR)

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.ShowModal()
        dlg.Destroy()
        # Refresh the footer in case the save folder changed
        self.footer_lbl.SetLabel(f"Saves to: {self._resolve_save_dir()}")
        self._rewrap()
        self.set_btn.SetFocus()

    def _status(self, msg, color=C_TEXT):
        if not hasattr(self, 'status_lbl'):
            _log("status called before UI ready: " + _short(msg))
            return
        self.status_lbl.SetLabel(msg)
        self.status_lbl.SetForegroundColour(wx.Colour(color))
        self._rewrap()


# ─── Startup ─────────────────────────────────────────────────────────────────
def _startup_grab():
    """Grab the URL or folder of the window the user was in (needs wx.App)."""
    grabbed = ""
    source_hwnd = 0
    try:
        st = load_settings()
        if st.get("grab_active_url", False):
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(fg, cls, 256)
            if cls.value in _ADDRESS_BAR_CLASSES:
                _log("grab: foreground window is supported — grabbing directly")
                source_hwnd = fg
                grabbed = grab_active_url(fg)
            else:
                _log(f"grab: foreground class '{cls.value}' is not usable — "
                     f"searching for a browser/Explorer window")
                hwnd = _find_browser_hwnd()
                if hwnd:
                    _log(f"grab: found browser hwnd={hwnd} — bringing it to front")
                    for _ in range(5):
                        user32.SetForegroundWindow(hwnd)
                        time.sleep(0.08)
                        if user32.GetForegroundWindow() == hwnd:
                            break
                    time.sleep(0.1)
                    source_hwnd = hwnd
                    grabbed = grab_active_url(hwnd)
                else:
                    _log("grab: no browser/Explorer window found")
        else:
            _log("grab: disabled in settings — skipped")
    except Exception as e:
        _log(f"startup grab error: {e!r}")
        grabbed = ""
    _log("grab: result: " + _short(grabbed or "(nothing)"))
    return grabbed, source_hwnd


def main():
    app = wx.App(False)
    try:
        app.MSWEnableDarkMode(wx.App.DarkMode_Always)
    except Exception:
        pass
    app.SetAppName("ZBookmarks")
    _log("ZBookmarks started")
    grabbed, source_hwnd = _startup_grab()
    win = MainWindow(grabbed_url=grabbed, source_hwnd=source_hwnd)
    win.Show()
    _activate(win)
    wx.CallLater(200, _activate, win)
    app.MainLoop()


if __name__ == "__main__":
    main()
