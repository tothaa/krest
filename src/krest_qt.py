#!/usr/bin/env python3

# import os
# import gc
import locale

# import sys
# import signal

import logging

# from importlib.resources import files

# from PySide6.QtGui import QGuiApplication
# from PySide6.QtCore import QUrl
# from PySide6.QtQml import QQmlApplicationEngine

from krest.krest_backend import setup_logging, KrestBackend
# from krest.translations import t


lang, encoding = locale.getdefaultlocale()

def qt():
    # TODO: QT/Kirigami UI

    return "This feature is yet not implemented"
    
    logging.info("connct backend...")
    backend = KrestBackend()
    print("File version: " + backend.file_data["version"])

    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    if not os.environ.get("QT_QUICK_CONTROLS_STYLE"):
        os.environ["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"

    base_path = files('krest').joinpath('qml', 'Main.qml')
    url = QUrl(f"{base_path}")

    engine.load(url)

    if len(engine.rootObjects()) == 0:
        quit()

    app.exec()

def main():
    setup_logging()
    logging.info("Start main()...")

    logging.info("start QT...")
    qt()

    logging.info("End main().")


if __name__ == "__main__":
    main()
