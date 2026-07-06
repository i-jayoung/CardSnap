import json
import os
from typing import List
from app.card_model import CardInfo

_DATA_DIR = os.path.join(os.path.expanduser("~"), ".cardsnap")
_DATA_FILE = os.path.join(_DATA_DIR, "cards.json")
_SETTINGS_FILE = os.path.join(_DATA_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "hotkey_screenshot": "Ctrl+Alt+C",
    "hotkey_clipboard": "Ctrl+Alt+V",
    "autostart": False,
    "auto_pin_on_recognize": True,
}


def _ensure_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# --- cards ---

def save_cards(cards: List[CardInfo]):
    _ensure_dir()
    data = [c.to_dict() for c in cards]
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cards() -> List[CardInfo]:
    if not os.path.exists(_DATA_FILE):
        return []
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [
            CardInfo(number=d["cn"], expiry=d["exp"], cvv=d["cvv"])
            for d in data
            if "cn" in d and "exp" in d and "cvv" in d
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


# --- settings ---

def save_settings(settings: dict):
    _ensure_dir()
    merged = {**DEFAULT_SETTINGS, **settings}
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    if not os.path.exists(_SETTINGS_FILE):
        return settings
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        settings.update(data)
    except (json.JSONDecodeError, TypeError):
        pass
    return settings


# --- backup / restore ---

BACKUP_VERSION = 1


def export_backup(filepath: str, cards: List[CardInfo]):
    data = {
        "version": BACKUP_VERSION,
        "app": "CardSnap",
        "settings": load_settings(),
        "cards": [c.to_dict() for c in cards],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_backup(filepath: str) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("app") != "CardSnap":
        raise ValueError("不是有效的 CardSnap 备份文件")

    result = {"settings": None, "cards": []}

    if "settings" in data and isinstance(data["settings"], dict):
        result["settings"] = data["settings"]

    if "cards" in data and isinstance(data["cards"], list):
        for d in data["cards"]:
            if "cn" in d and "exp" in d and "cvv" in d:
                result["cards"].append(
                    CardInfo(number=d["cn"], expiry=d["exp"], cvv=d["cvv"])
                )

    return result
