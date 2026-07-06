"""
Nuitka packaging script for CardSnap.
Produces a single standalone EXE with all dependencies and resources bundled.

Usage (run with GLOBAL python, not venv):
    python build.py
"""

import subprocess
import sys
import os
import shutil

APP_NAME = "CardSnap"
MAIN_SCRIPT = "main.py"
ICON_PATH = os.path.join("app", "resources", "icons", "app_icon.ico")

INCLUDE_DATA_FILES = [
    ("app/resources/styles.qss", "app/resources/"),
    ("app/resources/icons/app_icon.svg", "app/resources/icons/"),
    ("app/resources/icons/app_icon.png", "app/resources/icons/"),
    ("app/resources/icons/app_icon.ico", "app/resources/icons/"),
    ("app/resources/icons/gear.svg", "app/resources/icons/"),
    ("app/resources/icons/checkbox-checked.svg", "app/resources/icons/"),
    ("app/resources/icons/checkbox-unchecked.svg", "app/resources/icons/"),
]


def find_venv_site_packages():
    venv_sp = os.path.join(".venv", "Lib", "site-packages")
    if os.path.isdir(venv_sp):
        return os.path.abspath(venv_sp)
    return None


def check_nuitka(python):
    try:
        r = subprocess.run(
            [python, "-m", "nuitka", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))

    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    global_python = shutil.which("python") or sys.executable

    if os.path.exists(venv_python) and check_nuitka(venv_python):
        python = venv_python
        print(f"Using venv Python (has Nuitka): {python}")
    elif check_nuitka(global_python):
        python = global_python
        print(f"Using global Python (has Nuitka): {python}")
    else:
        print("ERROR: Nuitka not found. Install with: pip install nuitka")
        sys.exit(1)

    cmd = [
        python, "-m", "nuitka",
        "--standalone",
        "--onefile",
        f"--output-filename={APP_NAME}.exe",
        f"--windows-icon-from-ico={ICON_PATH}",
        "--windows-console-mode=disable",
        "--enable-plugin=pyside6",
        "--follow-imports",
        "--assume-yes-for-downloads",
        "--include-package=rapidocr_onnxruntime",
        "--include-package=onnxruntime",
        "--include-package-data=rapidocr_onnxruntime",
        "--include-package-data=onnxruntime",
    ]

    env = os.environ.copy()
    venv_sp = find_venv_site_packages()
    if venv_sp and python != venv_python:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = venv_sp + (";" + existing if existing else "")
        print(f"PYTHONPATH += {venv_sp}")

    for src, dst in INCLUDE_DATA_FILES:
        cmd.append(f"--include-data-files={src}={dst}")

    cmd.append(MAIN_SCRIPT)

    print()
    print("=" * 60)
    print(f"  Building {APP_NAME} with Nuitka (single EXE)")
    print("=" * 60)
    print()
    print("Full command:")
    print("  " + " \\\n    ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=project_dir, env=env)

    if result.returncode == 0:
        print()
        print("=" * 60)
        print(f"  BUILD SUCCESS!")
        print(f"  Output: {APP_NAME}.exe")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("  BUILD FAILED. Check errors above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    build()
