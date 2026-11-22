#!/usr/bin/env python3
"""Sun Launcher."""
import argparse
import logging
import sys

from sun import paths as P


def setup_logging():
    P.ensure_dirs()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.FileHandler(P.LOG, encoding="utf-8")
    sh = logging.StreamHandler()
    for h in (fh, sh):
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[fh, sh], force=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="диагностика без GUI")
    args = ap.parse_args()
    setup_logging()

    try:
        import minecraft_launcher_lib as mll
        import requests
        from PySide6.QtWidgets import QApplication
    except ImportError as e:
        print("Не хватает:", e)
        print("pip install -r requirements.txt")
        sys.exit(1)

    if args.check:
        from sun import backend as B
        print("Данные:", P.DATA)
        print("Профили:", [p["name"] for p in P.list_profiles()])
        vs = B.fetch_versions()
        rel = [v["id"] for v in vs if v["type"] == "release"]
        print("Версий:", len(rel), "| последняя:", rel[0] if rel else "—")
        if rel:
            print("Проверяю Java для", rel[0], "…")
            try:
                mll.install.install_minecraft_version(rel[0], str(P.GAME))
                j = B.ensure_java(rel[0], None, print)
                print("Java:", j or "НЕ НАЙДЕНА")
            except Exception as e:
                print("Ошибка:", e)
        return

    from sun.theme import QSS
    from sun.window import SunWindow
    app = QApplication(sys.argv)
    app.setApplicationName("Sun Launcher")
    app.setStyleSheet(QSS)
    win = SunWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()