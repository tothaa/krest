#!/usr/bin/env python3

import argparse
import ctypes
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile


DESKTOP_ID = "org.kde.krest.desktop"
FILE_DESKTOP_ID = "org.kde.krest.file.desktop"

SCRIPT = """
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
$folder = Join-Path ($shell.SpecialFolders.Item('Programs')) 'KREST'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$link = $shell.CreateShortcut((Join-Path $folder 'KREST.lnk'))
$link.TargetPath = $env:KREST_EXECUTABLE
$link.IconLocation = $env:KREST_ICON + ',0'
$link.WorkingDirectory = $env:USERPROFILE
$link.Save()
"""

def installed_asset(relative):
    dist = distribution("krest-utils")
    for entry in dist.files or ():
        if str(entry).replace("\\", "/").endswith("/" + relative):
            path = Path(dist.locate_file(entry))
            if path.is_file():
                return path
    raise FileNotFoundError(f"Missing installed asset: {relative}; reinstall krest-utils")

def tui_executable():
    name = "krest-tui.exe" if sys.platform == "win32" else "krest-tui"
    for directory in (Path(sys.executable).parent, Path(sysconfig.get_path("scripts"))):
        candidate = directory / name
        if candidate.is_file():
            return candidate.absolute()
    found = shutil.which(name)
    if found:
        return Path(found).absolute()
    raise FileNotFoundError("krest-tui was not found; reinstall krest-utils")

def copy_asset(relative, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(installed_asset(relative), destination)

def desktop_quote(value):
    value = str(value).replace("%", "%%")
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, "\\" + character)
    return '"' + value.replace("\\", "\\\\") + '"'

def install_linux(executable):
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    for category, name in (("apps", "krest"), ("mimetypes", "application-x-krest")):
        copy_asset("share/krest/krest-icon-dark2-256.png", data / f"icons/hicolor/256x256/{category}/{name}.png")
    copy_asset("share/mime/packages/krest.xml", data / "mime/packages/krest.xml")
    applications = data / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    for desktop_id in (DESKTOP_ID, FILE_DESKTOP_ID):
        launcher = installed_asset("share/applications/" + desktop_id).read_text(encoding="utf-8")
        launcher = launcher.replace("TryExec=krest-tui\n", "")
        launcher = launcher.replace("Exec=krest-tui", f"Exec={desktop_quote(executable)}")
        (applications / desktop_id).write_text(launcher, encoding="utf-8")
    for command, target in (("update-mime-database", data / "mime"), ("update-desktop-database", applications)):
        if shutil.which(command):
            subprocess.run([command, str(target)], check=True)
    print(f"Installed {applications / DESKTOP_ID}")
    print("Choose KREST in Open With for .krest files, or run:\n"
          f"  xdg-mime default {FILE_DESKTOP_ID} application/x-krest")

def install_windows(executable):
    import winreg

    icon = Path(os.environ["LOCALAPPDATA"]) / "KREST" / "krest.ico"
    copy_asset("share/krest/krest-windows-icon-dark2.ico", icon)

    def register(key, name, value):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + key) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_SZ, value)

    register("KREST.Document", "", "KREST Document")
    register("KREST.Document\\DefaultIcon", "", f'"{icon}",0')
    register("KREST.Document\\shell\\open\\command", "", f'"{executable}" -f "%1"')
    register(".krest\\OpenWithProgids", "KREST.Document", "")

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\.krest") as handle:
        try:
            winreg.QueryValueEx(handle, "")
        except FileNotFoundError:
            winreg.SetValueEx(handle, "", 0, winreg.REG_SZ, "KREST.Document")

    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", SCRIPT], env={**os.environ, "KREST_EXECUTABLE": str(executable), "KREST_ICON": str(icon)}, check=True)
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    print("Installed KREST in the Start menu with the dark2 icon.")
    print("If .krest already has a default app, choose KREST using Open With.")

def mac_script(executable):
    command = json.dumps(shlex.quote(str(executable)), ensure_ascii=False)
    return f'''on run
    my launchKrest("")
end run

on open openedFiles
    repeat with openedFile in openedFiles
        my launchKrest(" -f " & quoted form of (POSIX path of openedFile))
    end repeat
end open

on launchKrest(arguments)
    tell application "Terminal"
        activate
        do script ({command} & arguments)
    end tell
end launchKrest
'''

def install_macos(executable):
    app = Path.home() / "Applications/KREST.app"
    app.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / "krest.applescript"
        source.write_text(mac_script(executable), encoding="utf-8")
        built = Path(temporary) / "KREST.app"
        subprocess.run(["osacompile", "-o", str(built), str(source)], check=True)
        copy_asset("share/krest/krest.icns", built / "Contents/Resources/krest.icns")
        plist = built / "Contents/Info.plist"
        with plist.open("rb") as stream:
            info = plistlib.load(stream)
        info.update({
            "CFBundleIdentifier": "org.kde.krest",
            "CFBundleName": "KREST",
            "CFBundleIconFile": "krest.icns",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "KREST Document",
                "CFBundleTypeRole": "Editor",
                "CFBundleTypeExtensions": ["krest"],
                "CFBundleTypeIconFile": "krest.icns",
                "LSHandlerRank": "Alternate",
            }],
        })
        with plist.open("wb") as stream:
            plistlib.dump(info, stream)
        subprocess.run(["codesign", "--force", "--sign", "-", str(built)], check=True)
        if app.exists():
            shutil.rmtree(app)
        shutil.copytree(built, app)

    subprocess.run(["/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister", "-f", str(app)], check=True)
    print(f"Installed {app}; choose KREST in Finder's Open With for .krest files.")

def main():
    parser = argparse.ArgumentParser(description="Install KREST's per-user terminal launcher and file associations")
    parser.parse_args()
    installers = {"linux": install_linux, "win32": install_windows, "darwin": install_macos}
    try:
        installer = installers[sys.platform]
    except KeyError:
        raise SystemExit(f"Desktop integration is unsupported on {sys.platform}") from None
    try:
        installer(tui_executable())
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Desktop integration failed: {error}") from error

if __name__ == "__main__":
    main()
