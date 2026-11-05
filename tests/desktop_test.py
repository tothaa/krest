"""Desktop setup tests that never modify the user's desktop or registry."""

import configparser
from contextlib import nullcontext
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import krest_post_install as desktop


ROOT = Path(__file__).resolve().parents[1]


def source_asset(relative):
    mapping = {
        'share/krest/krest-icon-dark2-256.png': 'unix/krest-icon-dark2-256.png',
        'share/krest/krest.icns': 'macos/krest.icns',
        'share/mime/packages/krest.xml': 'unix/krest.xml',
    }
    return ROOT / 'packaging' / mapping.get(relative, 'unix/' + relative.rsplit('/', 1)[-1])


class DesktopTests(unittest.TestCase):
    def test_linux_menu_and_document_handler_have_distinct_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            executable = data / 'Python environment' / 'krest-tui'
            with patch.dict(os.environ, {'XDG_DATA_HOME': temporary}), \
                    patch.object(desktop, 'installed_asset', side_effect=source_asset), \
                    patch.object(desktop.shutil, 'which', return_value=None):
                desktop.install_linux(executable)
            for desktop_id, arguments in ((desktop.DESKTOP_ID, ''),
                                          (desktop.FILE_DESKTOP_ID, ' -f %f')):
                parser = configparser.ConfigParser(interpolation=None)
                launcher = data / 'applications' / desktop_id
                parser.read(launcher)
                entry = parser['Desktop Entry']
                self.assertEqual(entry['Exec'], f'"{executable}"' + arguments)
                self.assertEqual(entry['Terminal'], 'true')
                if desktop_id == desktop.FILE_DESKTOP_ID:
                    self.assertEqual(entry['MimeType'], 'application/x-krest;')
                if desktop.shutil.which('desktop-file-validate'):
                    subprocess.run(['desktop-file-validate', str(launcher)], check=True)
            original = source_asset('share/krest/krest-icon-dark2-256.png').read_bytes()
            for name in ('apps/krest.png', 'mimetypes/application-x-krest.png'):
                self.assertEqual((data / 'icons/hicolor/256x256' / name).read_bytes(), original)

    def test_macos_bundle_registers_documents_and_terminal_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                if command[0] == 'osacompile':
                    bundle = Path(command[2])
                    (bundle / 'Contents/Resources').mkdir(parents=True)
                    with (bundle / 'Contents/Info.plist').open('wb') as stream:
                        plistlib.dump({'CFBundleExecutable': 'applet'}, stream)

            with patch.object(desktop.Path, 'home', return_value=home), \
                    patch.object(desktop, 'installed_asset', side_effect=source_asset), \
                    patch.object(desktop.subprocess, 'run', side_effect=run):
                desktop.install_macos(Path('/Python environment/bin/krest-tui'))
            app = home / 'Applications/KREST.app'
            with (app / 'Contents/Info.plist').open('rb') as stream:
                info = plistlib.load(stream)
            self.assertEqual(info['CFBundleDocumentTypes'][0]['CFBundleTypeExtensions'], ['krest'])
            self.assertEqual(info['CFBundleIconFile'], 'krest.icns')
            self.assertEqual(calls[-2][0], 'codesign')
            self.assertEqual(calls[-1][-1], str(app))
            script = desktop.mac_script(Path("/Python's environment/bin/krest-tui"))
            self.assertIn('tell application "Terminal"', script)
            self.assertIn('quoted form of (POSIX path of openedFile)', script)
            self.assertIn('my launchKrest(" -f "', script)

    def test_macos_icon_embeds_the_dark2_256_png(self):
        png = source_asset('share/krest/krest-icon-dark2-256.png').read_bytes()
        icon = source_asset('share/krest/krest.icns').read_bytes()
        self.assertEqual(icon[:4], b'icns')
        self.assertEqual(icon[8:12], b'ic08')
        self.assertEqual(int.from_bytes(icon[4:8], 'big'), len(icon))
        self.assertEqual(icon[16:], png)

    def test_windows_shortcut_and_file_command_use_same_environment(self):
        values = {}

        def query(key, name):
            if (key, name) not in values:
                raise FileNotFoundError
            return values[key, name], 1

        registry = SimpleNamespace(
            HKEY_CURRENT_USER=0, REG_SZ=1,
            CreateKey=lambda root, key: nullcontext(key),
            SetValueEx=lambda key, name, reserved, kind, value: values.update({(key, name): value}),
            QueryValueEx=query,
        )
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / 'Python environment/krest-tui.exe'
            with patch.dict('sys.modules', {'winreg': registry}), \
                    patch.dict(os.environ, {'LOCALAPPDATA': temporary}), \
                    patch.object(desktop, 'copy_asset'), \
                    patch.object(desktop.ctypes, 'windll', create=True), \
                    patch.object(desktop.subprocess, 'run') as run:
                desktop.install_windows(executable)
            command = values['Software\\Classes\\KREST.Document\\shell\\open\\command', '']
            self.assertEqual(command, f'"{executable}" -f "%1"')
            environment = run.call_args.kwargs['env']
            self.assertEqual(environment['KREST_EXECUTABLE'], str(executable))
            self.assertEqual(environment['KREST_ICON'], str(Path(temporary) / 'KREST/krest.ico'))


if __name__ == '__main__':
    unittest.main()
