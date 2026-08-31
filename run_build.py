"""Build NOC_Scheduler_V2.exe from this folder's .venv (no hardcoded machine paths)."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_SCRIPTS = os.path.join(HERE, ".venv", "Scripts")
PYINSTALLER = os.path.join(VENV_SCRIPTS, "pyinstaller.exe")
VENV_PYTHON = os.path.join(VENV_SCRIPTS, "python.exe")


def _fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def _conda_bin() -> str:
    candidates = []
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    if conda_prefix:
        candidates.append(os.path.join(conda_prefix, "Library", "bin"))
    home = os.path.expanduser("~")
    candidates.extend(
        [
            os.path.join(home, "anaconda3", "Library", "bin"),
            os.path.join(home, "miniconda3", "Library", "bin"),
            os.path.join(home, "Anaconda3", "Library", "bin"),
        ]
    )
    for path in candidates:
        if os.path.isfile(os.path.join(path, "tk86t.dll")):
            return path
    return ""


def main() -> None:
    if not os.path.isfile(PYINSTALLER):
        _fail(f"PyInstaller not found at {PYINSTALLER}\nCreate .venv here and pip install -r requirements.txt")

    sys.path.insert(0, HERE)
    import customtkinter
    import pulp

    ctk_path = os.path.dirname(customtkinter.__file__)
    cbc_path = os.path.join(os.path.dirname(pulp.__file__), "solverdir", "cbc", "win", "i64", "cbc.exe")
    if not os.path.isfile(cbc_path):
        _fail(f"PuLP CBC solver not found at {cbc_path}")

    args = [
        PYINSTALLER,
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "NOC_Scheduler_V2",
        "--add-data",
        f"{ctk_path}{os.pathsep}customtkinter/",
        "--add-binary",
        f"{cbc_path}{os.pathsep}.",
    ]

    ana = _conda_bin()
    if ana:
        tcl_lib = os.path.normpath(os.path.join(ana, "..", "lib", "tcl8.6"))
        tk_lib = os.path.normpath(os.path.join(ana, "..", "lib", "tk8.6"))
        extra_dlls = [
            "tk86t.dll",
            "tcl86t.dll",
            "libssl-3-x64.dll",
            "libcrypto-3-x64.dll",
            "ffi.dll",
            "libexpat.dll",
            "liblzma.dll",
            "libbz2.dll",
        ]
        for dll in extra_dlls:
            full = os.path.join(ana, dll)
            if os.path.isfile(full):
                args.extend(["--add-binary", f"{full}{os.pathsep}."])
        if os.path.isdir(tcl_lib):
            args.extend(["--add-data", f"{tcl_lib}{os.pathsep}tcl\\tcl8.6"])
        if os.path.isdir(tk_lib):
            args.extend(["--add-data", f"{tk_lib}{os.pathsep}tcl\\tk8.6"])
        print(f"Bundling extra Tcl/Tk DLLs from: {ana}")
    else:
        print("Anaconda Tcl/Tk DLLs not found — building with default Python Tk.")

    args.append("main.py")
    print("Running PyInstaller:")
    for a in args:
        print(" ", a)
    result = subprocess.run(args, cwd=HERE)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
