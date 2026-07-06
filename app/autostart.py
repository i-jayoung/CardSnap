import sys
import os
import winreg

APP_NAME = "CardSnap"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _is_compiled() -> bool:
    if getattr(sys, 'frozen', False):
        return True
    exe_name = os.path.basename(sys.executable).lower()
    return not exe_name.startswith('python')


def _get_exe_path() -> str:
    if _is_compiled():
        return f'"{sys.executable}" --minimized'
    else:
        python = sys.executable
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))
        pythonw = python.replace('python.exe', 'pythonw.exe')
        if os.path.exists(pythonw):
            python = pythonw
        return f'"{python}" "{script}" --minimized'


def is_autostart_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


def set_autostart(enabled: bool):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_READ
        )
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_path())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError:
        pass
