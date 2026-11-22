"""Свой сервер + bore. Отдельный мир."""
import logging
import re
import subprocess
import threading
from pathlib import Path

import minecraft_launcher_lib as mll
import requests

from sun import paths as P
from sun.backend import download, ensure_bore, ensure_java, NOWIN

LOG = logging.getLogger("sun.host")


def set_prop(path, key, value):
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, found = [], False
    for ln in lines:
        if ln.startswith(key + "="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


JOIN_RE = re.compile(r":\s*(\w+) joined the game")
LEAVE_RE = re.compile(r":\s*(\w+) left the game")


class Host:
    def __init__(self, be):
        self.be = be
        self.server = None
        self.tunnel = None
        self.address = ""
        self.players = set()

    def running(self):
        return self.server is not None

    def start(self, mc, ram, relay):
        be = self.be
        if self.running():
            be.toast("Сервер уже запущен", "warning")
            return
        self.players = set()
        try:
            cb = be.callback()
            be.status(f"Файлы {mc}…")
            mll.install.install_minecraft_version(mc, str(P.GAME), callback=cb)
            java = ensure_java(mc, cb, be.status)
            if not java:
                raise RuntimeError("Java не найдена — сервер не запустить")

            sdir = P.SERVERS / mc
            sdir.mkdir(parents=True, exist_ok=True)
            jar = sdir / "server.jar"
            if not jar.exists():
                be.status("Скачиваю сервер…")
                man = requests.get(P.MANIFEST, timeout=30, headers=P.UA).json()
                entry = next((v for v in man["versions"] if v["id"] == mc), None)
                if not entry:
                    raise RuntimeError(f"{mc} не найдена")
                meta = requests.get(entry["url"], timeout=30, headers=P.UA).json()
                dl = meta.get("downloads", {}).get("server")
                if not dl:
                    raise RuntimeError(f"Для {mc} нет серверного jar")
                download(dl["url"], jar, be.progress, dl.get("sha1"))

            (sdir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            props = sdir / "server.properties"
            set_prop(props, "online-mode", "false")
            set_prop(props, "server-port", str(P.LOCAL_PORT))
            set_prop(props, "motd", "Sun Launcher")

            be.status("Запускаю сервер…")
            self.server = subprocess.Popen(
                [java, f"-Xmx{ram}G", "-Xms512M", "-jar", "server.jar", "nogui"],
                cwd=str(sdir), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", bufsize=1, **NOWIN)
            threading.Thread(target=self._pipe_server, daemon=True).start()

            be.status("Готовлю туннель…")
            bore = ensure_bore(be.progress)
            self.tunnel = subprocess.Popen(
                [str(bore), "local", str(P.LOCAL_PORT), "--to", relay],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", **NOWIN)
            threading.Thread(target=self._pipe_tunnel, args=(relay, mc), daemon=True).start()
            be.emit("host", {"state": "on", "players": []})
        except Exception:
            # Не оставляем осиротевший процесс сервера, если туннель или
            # загрузка не удались — иначе running() навсегда вернёт True.
            self.stop()
            raise

    def _pipe_server(self):
        proc = self.server
        try:
            for line in proc.stdout:
                line = line.rstrip()
                self.be.log("[server] " + line)
                jm = JOIN_RE.search(line)
                lm = LEAVE_RE.search(line)
                changed = False
                if jm:
                    self.players.add(jm.group(1))
                    changed = True
                elif lm:
                    self.players.discard(lm.group(1))
                    changed = True
                if changed:
                    self.be.emit("host", {"players": sorted(self.players)})
        except Exception:
            pass
        self.be.log("[server] завершился")
        if proc is self.server:
            self.stop()

    def _pipe_tunnel(self, relay, mc):
        proc = self.tunnel
        try:
            for line in proc.stdout:
                m = re.search(re.escape(relay) + r":(\d+)", line)
                if m:
                    self.address = f"{relay}:{m.group(1)}"
                    self.be.emit("host", {"address": self.address, "mc": mc})
                    self.be.log(f"Адрес: {self.address}")
                    self.be.toast("Адрес готов", "success")
                else:
                    self.be.log("[tunnel] " + line.rstrip())
        except Exception:
            pass

    def stop(self):
        tunnel, server = self.tunnel, self.server
        self.tunnel = self.server = None
        self.address = ""
        self.players = set()
        if tunnel:
            try:
                tunnel.terminate()
            except Exception:
                pass
        if server:
            try:
                server.stdin.write("stop\n")
                server.stdin.flush()
            except Exception:
                pass

            def reap():
                try:
                    server.wait(timeout=30)
                except Exception:
                    try:
                        server.kill()
                    except Exception:
                        pass
            threading.Thread(target=reap, daemon=True).start()
        self.be.emit("host", {"state": "off", "players": []})

    def command(self, cmd):
        if self.server and self.server.stdin:
            try:
                self.server.stdin.write(cmd + "\n")
                self.server.stdin.flush()
                return True
            except Exception as e:
                self.be.log(f"Команда: {e}")
        return False