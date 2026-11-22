"""Пути, конфиг, профили. НЕ импортирует другие модули sun."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

APP = "sun-launcher"
IS_WIN = sys.platform == "win32"

if IS_WIN:
    DATA = Path(os.environ.get("APPDATA") or Path.home()) / APP
else:
    DATA = Path.home() / ".local/share" / APP

GAME = DATA / "minecraft"
INST = DATA / "instances"
SERVERS = DATA / "servers"
BIN = DATA / "bin"
TMP = DATA / "tmp"
CFG = DATA / "config.json"
LOG = DATA / "launcher.log"
VCACHE = DATA / "versions_cache.json"

MR = "https://api.modrinth.com/v2"
UA = {"User-Agent": "SunLauncher/1.0"}
MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
LOCAL_PORT = 25565

LOADERS = ["vanilla", "fabric", "quilt", "forge"]
LOADER_LABEL = {"vanilla": "ВАНИЛЛА", "fabric": "FABRIC",
                "quilt": "QUILT", "forge": "FORGE"}
LOADER_COLOR = {"vanilla": "#6a9955", "fabric": "#dbb877",
                "quilt": "#b060d0", "forge": "#e08a3c"}

TYPES = {"Моды": "mod", "Шейдеры": "shader", "Ресурспаки": "resourcepack"}
FOLDERS = {"mod": "mods", "shader": "shaderpacks", "resourcepack": "resourcepacks"}


def ensure_dirs():
    for d in (DATA, GAME, INST, SERVERS, BIN, TMP):
        d.mkdir(parents=True, exist_ok=True)


def defaults():
    return {"nick": "Player", "ram": 3, "cur": "", "mc": "", "addr": "",
            "relay": "bore.pub", "eula": False, "page": "home", "jvm_extra": ""}


def load_cfg():
    ensure_dirs()
    d = defaults()
    try:
        d.update(json.loads(CFG.read_text(encoding="utf-8")))
    except Exception:
        pass
    return d


def save_cfg(cfg):
    ensure_dirs()
    tmp = CFG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CFG)


def clean_name(s):
    return re.sub(r"[^\w\-. ]", "_", s or "").strip()[:48]


def inst_dir(name):
    return INST / name


def game_dir(name):
    return INST / name / "game"


def read_meta(name):
    try:
        return json.loads((inst_dir(name) / "instance.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_meta(name, data):
    inst_dir(name).mkdir(parents=True, exist_ok=True)
    (inst_dir(name) / "instance.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_profiles():
    if not INST.exists():
        return []
    out = []
    for p in sorted(INST.iterdir()):
        if (p / "instance.json").exists():
            m = read_meta(p.name)
            m["name"] = p.name
            out.append(m)
    out.sort(key=lambda x: x.get("last_played") or 0, reverse=True)
    return out


def count_files(name, kind="mod"):
    d = game_dir(name) / FOLDERS.get(kind, "mods")
    try:
        return len([p for p in d.iterdir() if p.is_file()])
    except OSError:
        return 0


def list_files(name, kind="mod"):
    d = game_dir(name) / FOLDERS.get(kind, "mods")
    try:
        return sorted(p.name for p in d.iterdir() if p.is_file())
    except OSError:
        return []


def safe_join(base, rel):
    base = Path(base).resolve()
    target = (base / str(rel)).resolve()
    if base != target and base not in target.parents:
        raise RuntimeError(f"Небезопасный путь: {rel}")
    return target


def open_path(p):
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    try:
        if IS_WIN:
            os.startfile(str(p))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        pass