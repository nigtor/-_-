"""Логика лаунчера через minecraft-launcher-lib."""
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

import minecraft_launcher_lib as mll
import requests

from sun import paths as P

LOG = logging.getLogger("sun.backend")
NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}
HAS_NEOFORGE = hasattr(mll, "neoforge")
CACHE_VERSIONS = P.DATA / "versions_cache.json"


def offline_uuid(name):
    h = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode()).digest())
    h[6] = h[6] & 0x0F | 0x30
    h[8] = h[8] & 0x3F | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


def download(url, dest, on_progress=None, sha1=None):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and sha1:
        try:
            if hashlib.sha1(dest.read_bytes()).hexdigest() == sha1:
                if on_progress:
                    on_progress(1, 1)
                return dest
        except OSError:
            pass
    tmp = dest.with_name(dest.name + ".part")
    with requests.get(url, stream=True, timeout=60, headers=P.UA) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done, total)
    if sha1 and hashlib.sha1(tmp.read_bytes()).hexdigest() != sha1:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Контрольная сумма не совпала: {dest.name}")
    tmp.replace(dest)
    return dest


def cached_versions():
    try:
        return json.loads(CACHE_VERSIONS.read_text(encoding="utf-8"))
    except Exception:
        return []


def fetch_versions():
    """Синхронно. Кэширует, чтобы диалог никогда не был пустым."""
    P.ensure_dirs()
    try:
        vs = mll.utils.get_version_list()
        if vs:
            CACHE_VERSIONS.write_text(json.dumps(vs), encoding="utf-8")
            return vs
    except Exception as e:
        LOG.warning("список версий: %s", e)
    return cached_versions()


def releases():
    return [v["id"] for v in fetch_versions() if v["type"] == "release"]


def supported_loaders():
    """NeoForge только если библиотека его умеет."""
    out = ["vanilla", "fabric", "quilt", "forge"]
    if HAS_NEOFORGE:
        out.append("neoforge")
    return out


def loader_id(loader, mc, lv=None):
    ids = [v["id"] for v in mll.utils.get_installed_versions(str(P.GAME))]
    if loader in ("fabric", "quilt"):
        c = [i for i in ids if i.startswith(f"{loader}-loader-") and i.endswith("-" + mc)]
        if lv:
            c = [i for i in c if f"-loader-{lv}-" in i] or c
    elif loader == "neoforge":
        c = [i for i in ids if "neoforge" in i.lower()]
        if lv:
            c = [i for i in c if lv in i] or c
    else:
        c = [i for i in ids
             if "forge" in i.lower() and mc in i and "neoforge" not in i.lower()]
        if lv:
            c = [i for i in c if lv in i] or c
    return sorted(c)[-1] if c else None


def ensure_java(version, callback=None, status=None):
    """Скачивает нужный JRE, если его нет. Возвращает путь или None.

    Это то, чего не хватало: get_executable_path сам ничего не качает.
    """
    try:
        info = mll.runtime.get_version_runtime_information(version, str(P.GAME))
    except Exception as e:
        LOG.debug("runtime info для %s: %s", version, e)
        info = None
    if not info:
        # старый формат: ищем системную Java
        exe = shutil.which("java")
        if exe:
            LOG.info("использую системную Java: %s", exe)
        return exe
    name = info["name"] if isinstance(info, dict) else str(info)
    exe = mll.runtime.get_executable_path(name, str(P.GAME))
    if exe and Path(exe).exists():
        return exe
    if status:
        status(f"Скачиваю Java ({name})…")
    try:
        kw = {"callback": callback} if callback else {}
        mll.runtime.install_jvm_runtime(name, str(P.GAME), **kw)
    except Exception as e:
        LOG.warning("не скачался рантайм %s: %s", name, e)
        return shutil.which("java")
    exe = mll.runtime.get_executable_path(name, str(P.GAME))
    if exe and Path(exe).exists():
        LOG.info("Java готова: %s", exe)
        return exe
    return shutil.which("java")


def ensure_bore(on_progress=None):
    exe = P.BIN / ("bore.exe" if os.name == "nt" else "bore")
    if exe.exists():
        return exe
    system = platform.system()
    arch = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    target = {"Windows": f"{arch}-pc-windows-msvc",
              "Darwin": f"{arch}-apple-darwin",
              "Linux": f"{arch}-unknown-linux-musl"}.get(system)
    rel = requests.get("https://api.github.com/repos/ekzhang/bore/releases/latest",
                       timeout=25, headers=P.UA).json()
    asset = next((a for a in rel.get("assets", []) if target and target in a["name"]), None)
    if not asset:
        raise RuntimeError(f"Нет сборки bore для {system}/{arch}")
    archive = P.BIN / asset["name"]
    download(asset["browser_download_url"], archive, on_progress)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            member = next(n for n in z.namelist() if n.endswith(exe.name))
            exe.write_bytes(z.read(member))
    else:
        with tarfile.open(archive) as t:
            member = next(m for m in t.getmembers()
                          if m.name.endswith(exe.name) and m.isfile())
            exe.write_bytes(t.extractfile(member).read())
    if os.name != "nt":
        exe.chmod(0o755)
    archive.unlink(missing_ok=True)
    return exe


class Backend:
    def __init__(self, emit):
        self.emit = emit
        self.cfg = P.load_cfg()
        self.proc = None
        self.busy = False
        self._versions = cached_versions()

    def log(self, t):
        LOG.info(t)
        self.emit("log", str(t))

    def status(self, t):
        self.emit("status", str(t))

    def progress(self, done, total):
        self.emit("progress", (done, max(1, total)))

    def toast(self, t, kind="info"):
        self.emit("toast", (str(t), kind))

    def save(self, patch=None):
        if patch:
            self.cfg.update(patch)
        P.save_cfg(self.cfg)

    def callback(self):
        mx = {"v": 1}
        return {"setStatus": lambda s: self.status(s),
                "setMax": lambda m: mx.__setitem__("v", max(m, 1)),
                "setProgress": lambda p: self.progress(p, mx["v"])}

    def job(self, title, fn, then=None):
        if self.busy:
            self.toast("Занят другой задачей", "warning")
            return
        self.busy = True
        self.emit("task", {"title": title, "state": "run"})

        def run():
            try:
                fn()
                self.emit("task", {"title": title, "state": "done"})
                if then:
                    then()
            except Exception as e:
                LOG.exception("job")
                self.emit("task", {"title": title, "state": "error"})
                self.toast(str(e), "error")
                self.log(f"Ошибка: {e}")
            finally:
                self.busy = False
                self.status("Готово")
        threading.Thread(target=run, daemon=True).start()

    def load_versions(self):
        if self._versions:
            self.emit("versions", self._versions)

        def run():
            vs = fetch_versions()
            if vs:
                self._versions = vs
                self.emit("versions", vs)
                rel = [v["id"] for v in vs if v["type"] == "release"]
                if not self.cfg.get("mc") and rel:
                    self.save({"mc": rel[0]})
            else:
                self.toast("Список версий недоступен — проверь интернет", "error")
        threading.Thread(target=run, daemon=True).start()

    def versions(self):
        if not self._versions:
            self._versions = fetch_versions()
        return self._versions

    def install_profile(self, name, mc, loader, lv=None, extra=None):
        P.GAME.mkdir(parents=True, exist_ok=True)
        cb = self.callback()
        self.status(f"Файлы Minecraft {mc}…")
        mll.install.install_minecraft_version(mc, str(P.GAME), callback=cb)

        # Java качаем ДО загрузчика — Forge/NeoForge запускают процессоры на Java
        java = ensure_java(mc, cb, self.status)

        if loader != "vanilla":
            self.status(f"Ставлю {loader}…")
            kw = {"callback": cb}
            if java:
                kw["java"] = java
            if loader == "fabric":
                mll.fabric.install_fabric(mc, str(P.GAME), loader_version=lv, **kw)
            elif loader == "quilt":
                mll.quilt.install_quilt(mc, str(P.GAME), loader_version=lv, **kw)
            elif loader == "forge":
                fv = f"{mc}-{lv}" if lv else mll.forge.find_forge_version(mc)
                if not fv:
                    raise RuntimeError(f"Для {mc} нет подходящего Forge")
                mll.forge.install_forge_version(fv, str(P.GAME), **kw)
            elif loader == "neoforge":
                if not HAS_NEOFORGE:
                    raise RuntimeError(
                        "Установленная minecraft-launcher-lib не умеет NeoForge.\n"
                        "Обнови: pip install -U minecraft-launcher-lib\n"
                        "Или выбери Forge.")
                nv = lv or mll.neoforge.get_latest_neoforge_version(mc)
                if not nv:
                    raise RuntimeError(f"Для {mc} нет NeoForge")
                mll.neoforge.install_neoforge_version(nv, str(P.GAME), **kw)

        launch_id = mc if loader == "vanilla" else loader_id(loader, mc, lv)
        if not launch_id:
            raise RuntimeError("Не нашёл установленную версию загрузчика")

        P.game_dir(name).mkdir(parents=True, exist_ok=True)
        meta = {"mc": mc, "loader": loader, "launch_id": launch_id,
                "loader_version": lv, "created": time.time(), "last_played": 0,
                "icon": "", "source": "manual"}
        if extra:
            meta.update(extra)
        P.write_meta(name, meta)
        return meta

    def create(self, name, mc, loader, lv=None):
        name = P.clean_name(name)
        if not name or not mc:
            self.toast("Укажи название и версию", "warning")
            return
        if name in [p["name"] for p in P.list_profiles()]:
            self.toast("Профиль с таким названием уже есть", "warning")
            return

        def work():
            self.install_profile(name, mc, loader, lv)
            self.save({"cur": name})
            self.toast(f"Профиль «{name}» готов", "success")
        self.job("Создание профиля", work,
                 then=lambda: self.emit("profiles", P.list_profiles()))

    def delete(self, name):
        shutil.rmtree(P.inst_dir(name), ignore_errors=True)
        if self.cfg.get("cur") == name:
            rest = P.list_profiles()
            self.save({"cur": rest[0]["name"] if rest else ""})
        self.emit("profiles", P.list_profiles())
        self.toast("Профиль удалён", "info")

    def set_icon(self, name, src):
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        pm = QPixmap(src)
        if pm.isNull():
            self.toast("Не читается как изображение", "error")
            return
        pm = pm.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        dst = P.inst_dir(name) / "icon.png"
        pm.save(str(dst), "PNG")
        m = P.read_meta(name)
        m["icon"] = str(dst)
        P.write_meta(name, m)
        self.emit("profiles", P.list_profiles())
        self.toast("Аватар обновлён", "success")

    def play(self, name=None, server=None):
        if self.busy:
            self.toast("Занят", "warning")
            return
        name = name or self.cfg.get("cur")
        if not name:
            self.toast("Сначала выбери профиль", "warning")
            return
        nick = (self.cfg.get("nick") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", nick):
            self.toast("Ник: 3–16 символов, латиница, цифры, _", "warning")
            return
        meta = P.read_meta(name)
        if not meta.get("launch_id"):
            self.toast("Профиль повреждён — пересоздай", "error")
            return
        ram = max(1, int(self.cfg.get("ram", 3)))
        gdir = P.game_dir(name)
        self.emit("game", "preparing")
        self.busy = True

        def run():
            try:
                cb = self.callback()
                self.status(f"Проверяю файлы {meta['mc']}…")
                mll.install.install_minecraft_version(meta["mc"], str(P.GAME), callback=cb)
                java = ensure_java(meta["mc"], cb, self.status)
                if not java:
                    raise RuntimeError(
                        "Java не найдена и не скачалась.\n"
                        "Поставь системную Java или проверь интернет.")
                opts = {"username": nick, "uuid": offline_uuid(nick), "token": "",
                        "launcherName": "Sun", "gameDirectory": str(gdir),
                        "executablePath": java,
                        "jvmArguments": [f"-Xmx{ram}G", "-Xms512M"]}
                extra = (self.cfg.get("jvm_extra") or "").split()
                if extra:
                    opts["jvmArguments"] += extra
                if server:
                    host, _, port = server.rpartition(":")
                    opts["server"] = host or server
                    opts["port"] = port if host else str(P.LOCAL_PORT)
                cmd = mll.command.get_minecraft_command(meta["launch_id"], str(P.GAME), opts)
                self.log(f"Запускаю «{name}» · {meta['mc']} · {meta['loader']}")
                self.log(f"Java: {java}")
                self.proc = subprocess.Popen(cmd, cwd=str(gdir), **NOWIN)
                self.emit("game", "running")
                meta["last_played"] = time.time()
                P.write_meta(name, meta)
                self.emit("profiles", P.list_profiles())
                code = self.proc.wait()
                if code != 0:
                    self.log(f"Игра завершилась с кодом {code}")
            except Exception as e:
                LOG.exception("play")
                self.toast(str(e), "error")
            finally:
                self.busy = False
                self.proc = None
                self.emit("game", "idle")
                self.status("Готово")
        threading.Thread(target=run, daemon=True).start()

    def stop_game(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def set_nick(self, n):
        n = (n or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", n):
            self.toast("Ник: 3–16 символов", "warning")
            return False
        self.save({"nick": n})
        self.emit("nick", n)
        return True