"""Modrinth: поиск, моды с зависимостями, сборки."""
import json
import logging
import zipfile
from pathlib import Path

import requests

from sun import paths as P
from sun.backend import download

LOG = logging.getLogger("sun.catalog")
E4MC_SLUG = "e4mc"


def search(query, ptype, mc=None, loader=None, limit=30):
    facets = [[f"project_type:{ptype}"]]
    if mc:
        facets.append([f"versions:{mc}"])
    if ptype == "mod" and loader and loader != "vanilla":
        cats = [loader] + (["fabric"] if loader == "quilt" else [])
        facets.append([f"categories:{c}" for c in cats])
    r = requests.get(f"{P.MR}/search",
                     params={"query": query, "facets": json.dumps(facets), "limit": limit},
                     headers=P.UA, timeout=25)
    r.raise_for_status()
    return r.json()["hits"]


def versions_of(pid, mc=None, loader=None):
    params = {}
    if mc:
        params["game_versions"] = json.dumps([mc])
    if loader and loader != "vanilla":
        params["loaders"] = json.dumps([loader] + (["fabric"] if loader == "quilt" else []))
    r = requests.get(f"{P.MR}/project/{pid}/version", params=params,
                     headers=P.UA, timeout=25)
    r.raise_for_status()
    return r.json()


def install_item(pid, ptype, profile, be, seen=None):
    seen = seen if seen is not None else set()
    if pid in seen:
        return
    seen.add(pid)
    meta = P.read_meta(profile)
    mc, loader = meta.get("mc"), meta.get("loader", "vanilla")
    vs = versions_of(pid, mc, loader if ptype == "mod" else None)
    if not vs:
        raise RuntimeError(f"Нет версии под {mc} / {loader}")
    v = vs[0]
    f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
    dest = P.game_dir(profile) / P.FOLDERS[ptype] / f["filename"]
    be.status(f"Скачиваю {f['filename']}…")
    download(f["url"], dest, be.progress, f.get("hashes", {}).get("sha1"))
    be.log(f"Установлено: {f['filename']}")
    if ptype == "mod":
        for d in v.get("dependencies", []):
            if d.get("dependency_type") == "required" and d.get("project_id"):
                install_item(d["project_id"], ptype, profile, be, seen)


def install_e4mc(profile, be):
    """Мод для коопа в своём одиночном мире."""
    meta = P.read_meta(profile)
    if meta.get("loader") not in ("fabric", "quilt"):
        raise RuntimeError("e4mc работает на Fabric или Quilt.\n"
                           "Создай профиль с Fabric и поставь мод туда.")
    r = requests.get(f"{P.MR}/project/{E4MC_SLUG}", headers=P.UA, timeout=25)
    r.raise_for_status()
    pid = r.json()["id"]
    install_item(pid, "mod", profile, be)
    be.log("e4mc установлен. В игре: Открыть для сети → появится адрес для друга.")


def install_pack(pid, name, be):
    vs = versions_of(pid)
    if not vs:
        raise RuntimeError("У сборки нет версий")
    f = next((x for x in vs[0]["files"] if x["filename"].endswith(".mrpack")), None)
    if not f:
        raise RuntimeError("Нет файла .mrpack")
    existing = [p["name"] for p in P.list_profiles()]
    base = P.clean_name(name) or "pack"
    name, n = base, 2
    while name in existing:
        name = f"{base}-{n}"
        n += 1
    tmp = P.TMP / f["filename"]
    be.status("Скачиваю сборку…")
    download(f["url"], tmp, be.progress)
    try:
        unpack_mrpack(tmp, name, be)
    finally:
        tmp.unlink(missing_ok=True)
    return name


def unpack_mrpack(path, name, be):
    with zipfile.ZipFile(path) as z:
        idx = json.loads(z.read("modrinth.index.json"))
        deps = idx["dependencies"]
        if "neoforge" in deps:
            raise RuntimeError("Сборки на NeoForge не поддерживаются библиотекой")
        loader, lv = "vanilla", None
        for key, ln in (("fabric-loader", "fabric"), ("quilt-loader", "quilt"),
                        ("forge", "forge")):
            if key in deps:
                loader, lv = ln, deps[key]
                break
        be.install_profile(name, deps["minecraft"], loader, lv,
                           extra={"source": "modrinth"})
        gdir = P.game_dir(name)
        files = [x for x in idx.get("files", [])
                 if x.get("env", {}).get("client") != "unsupported"]
        for i, x in enumerate(files, 1):
            target = P.safe_join(gdir, x["path"])
            be.status(f"Файл {i}/{len(files)}: {target.name}")
            urls = x.get("downloads") or []
            if urls:
                download(urls[0], target, None, x.get("hashes", {}).get("sha1"))
            be.progress(i, len(files))
        for prefix in ("overrides/", "client-overrides/"):
            for n in z.namelist():
                if n.startswith(prefix) and not n.endswith("/"):
                    target = P.safe_join(gdir, n[len(prefix):])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(n))
    be.log(f"Сборка «{name}» установлена")


def import_mrpack(path, be):
    name = P.clean_name(Path(path).stem) or "imported"
    existing = [p["name"] for p in P.list_profiles()]
    base, n = name, 2
    while name in existing:
        name = f"{base}-{n}"
        n += 1
    unpack_mrpack(Path(path), name, be)
    return name