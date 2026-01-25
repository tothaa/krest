#!/usr/bin/env python3

pass

# import os
# import sys
# import logging
#
# def user_log_dir(appname: str | None = None) -> str:
#     # better solution: https://pypi.org/project/platformdirs/
#     # from platformdirs import user_log_dir
#
#     if sys.platform == "win32":
#         # Windows
#         path = os.environ.get("LOCALAPPDATA")
#         if not path:
#             path = os.path.expanduser("~\\AppData\\Local")
#         if appname:
#             path = os.path.join(path, appname, "Logs")
#         else:
#             path = os.path.join(path, "Logs")
#
#     elif sys.platform == "darwin":
#         # macOS
#         path = os.path.expanduser("~/Library/Logs")
#         if appname:
#             path = os.path.join(path, appname)
#
#     elif (os.getenv("ANDROID_DATA") == "/data" and os.getenv("ANDROID_ROOT") == "/system"):
#         # Android
#         base = None
#         try:
#             from android import mActivity  # type: ignore
#             context = mActivity.getApplicationContext()
#             base = context.getCacheDir().getAbsolutePath()
#         except Exception:
#             try:
#                 from jnius import autoclass  # type: ignore
#                 context = autoclass("android.content.Context")
#                 base = context.getCacheDir().getAbsolutePath()
#             except Exception:
#                 import re
#                 pattern = re.compile(r"/data/(data|user/\d+)/(.+)/files")
#                 for p in sys.path:
#                     match = pattern.match(p)
#                     if match:
#                         base = p.split("/files")[0] + "/cache"
#         if base is None:
#             base = "/data/data/unknown/cache"
#
#         if appname:
#             path = os.path.join(base, appname, "log")
#         else:
#             path = os.path.join(base, "log")
#     else:
#         # Linux/Unix
#         state_home = os.environ.get("XDG_STATE_HOME")
#         if not state_home or not state_home.strip():
#             state_home = os.path.expanduser("~/.local/state")
#
#         if appname:
#             path = os.path.join(state_home, appname, "log")
#         else:
#             path = os.path.join(state_home, "log")
#
#     return path
#
# def setup_logging():
#     log_dir = user_log_dir("Krest")
#     os.makedirs(log_dir, exist_ok=True)
#     log_file = os.path.join(log_dir, 'krest.log')
#     print("[I] Log File:", log_file)
#     logging.basicConfig(filename=log_file, level=logging.DEBUG, force=True)
#
# setup_logging()
#
