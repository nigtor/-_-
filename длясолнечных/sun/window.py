"""Главное окно."""
import threading

from PySide6.QtCore import (Qt, QObject, Signal, QTimer, QPropertyAnimation,
                            QEasingCurve)
from PySide6.QtWidgets import (QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QLabel, QPushButton, QLineEdit,
                               QListWidget, QListWidgetItem, QSlider, QCheckBox,
                               QComboBox, QStackedWidget, QFileDialog,
                               QGraphicsOpacityEffect, QScrollArea, QPlainTextEdit,
                               QMessageBox, QMenu, QTreeWidget, QTreeWidgetItem,
                               QApplication)

from sun import paths as P
from sun import catalog, theme as T
from sun.backend import Backend
from sun.host import Host
from sun.widgets import (SunButton, Panel, SunLogo, SunCanvas, ShimmerProgress,
                         Toast, ProfileCard, badge, pixmap_or_default, human_when)
from sun.dialogs import CreateDialog, TargetDialog, ContentsDialog


class Bridge(QObject):
    evt = Signal(str, object)

    def emit_evt(self, event, payload):
        self.evt.emit(event, payload)


class SunWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bridge = Bridge()
        self.be = Backend(self.bridge.emit_evt)
        self.host = Host(self.be)
        self.pages = {}
        self.cards = {}
        self.recent_cards = {}
        self.selected = None
        self.profiles = []
        self.versions = []
        self.hits = {"mods": [], "packs": []}
        self.toasts = []
        self._page_anim = None
        self._online_badges = []

        self.setWindowTitle("Sun Launcher")
        self.resize(1340, 880)
        self.setMinimumSize(1080, 700)
        self.setWindowFlags(Qt.FramelessWindowHint)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(160)
        self._timer.timeout.connect(self._render_versions)

        self._build()
        self._wire()
        self._load()
        self.bridge.evt.connect(self._on_event)

    def panel(self, accent=False):
        return Panel(accent)

    def _build(self):
        root = SunCanvas()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        tb = QWidget()
        tb.setObjectName("titlebar")
        tb.setFixedHeight(52)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(14, 0, 6, 0)
        tl.setSpacing(8)
        mark = SunLogo(20, pad=8)
        logo = QLabel("SUN")
        logo.setObjectName("logo")
        sub = QLabel("LAUNCHER")
        sub.setObjectName("sub")
        tl.addWidget(mark)
        tl.addWidget(logo)
        tl.addWidget(sub)
        tl.addStretch(1)
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("win")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("win")
        for b in (self.btn_min, self.btn_close):
            b.setFixedSize(38, 30)
        tl.addWidget(self.btn_min)
        tl.addWidget(self.btn_close)
        tb.mousePressEvent = self._tb_press
        for c in (mark, logo, sub):
            c.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        outer.addWidget(tb)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, 1)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(224)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 16, 14, 14)
        sl.setSpacing(4)
        sl.addWidget(SunLogo(66), 0, Qt.AlignHCenter)
        sl.addSpacing(10)
        self.nav = {}
        for key, label, ico in [("home", "ГЛАВНАЯ", "☀"), ("versions", "ВЕРСИИ", "≡"),
                                ("mods", "МОДЫ", "◈"), ("packs", "СБОРКИ", "▤"),
                                ("profiles", "ПРОФИЛИ", "▣"), ("net", "СЕТЬ", "⇄"),
                                ("settings", "НАСТРОЙКИ", "⚙")]:
            b = QPushButton(f"  {ico}   {label}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.nav[key] = b
            sl.addWidget(b)
        sl.addStretch(1)
        ab = QWidget()
        ab.setObjectName("accbox")
        abl = QVBoxLayout(ab)
        abl.setContentsMargins(10, 8, 10, 8)
        abl.setSpacing(2)
        cap = QLabel("НИК")
        cap.setObjectName("tiny")
        self.nick_label = QLabel("Player")
        self.nick_label.setObjectName("accname")
        abl.addWidget(cap)
        abl.addWidget(self.nick_label)
        sl.addWidget(ab)
        body.addWidget(side)

        right = QVBoxLayout()
        right.setContentsMargins(20, 18, 20, 14)
        right.setSpacing(12)
        body.addLayout(right, 1)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)

        dock = self.panel()
        dl = QVBoxLayout(dock)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(6)
        row = QHBoxLayout()
        self.task_title = QLabel("Готово")
        self.task_pct = QLabel("")
        self.task_pct.setObjectName("accent")
        row.addWidget(self.task_title)
        row.addStretch(1)
        row.addWidget(self.task_pct)
        dl.addLayout(row)
        self.bar = ShimmerProgress()
        dl.addWidget(self.bar)
        self.status_lb = QLabel("")
        self.status_lb.setObjectName("muted")
        dl.addWidget(self.status_lb)
        dock.hide()
        self.dock = dock
        right.addWidget(dock)

        self._page_home()
        self._page_versions()
        self._page_catalog("mods")
        self._page_catalog("packs")
        self._page_profiles()
        self._page_net()
        self._page_settings()

    def _add(self, k, w):
        self.pages[k] = w
        self.stack.addWidget(w)

    def _scroll(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setObjectName("scroll")
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("clear")
        il = QVBoxLayout(inner)
        il.setSpacing(12)
        il.setContentsMargins(0, 0, 12, 0)
        sc.setWidget(inner)
        l.addWidget(sc)
        return w, il

    def _page_home(self):
        w, l = self._scroll()
        hero = self.panel(True)
        hl = QHBoxLayout(hero)
        hl.setContentsMargins(26, 26, 26, 26)
        hl.setSpacing(24)
        self.hero_icon = QLabel()
        self.hero_icon.setFixedSize(124, 124)
        self.hero_icon.setObjectName("avatar")
        self.hero_icon.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.hero_icon)
        col = QVBoxLayout()
        col.setSpacing(6)
        cap = QLabel("АКТИВНЫЙ ПРОФИЛЬ")
        cap.setObjectName("tiny")
        self.hero_name = QLabel("Профиль не выбран")
        self.hero_name.setObjectName("h1")
        self.hero_chips = QHBoxLayout()
        self.hero_chips.setSpacing(5)
        self.hero_meta = QLabel("—")
        self.hero_meta.setObjectName("muted")
        col.addWidget(cap)
        col.addWidget(self.hero_name)
        col.addLayout(self.hero_chips)
        col.addWidget(self.hero_meta)
        col.addSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.play_btn = SunButton("▶   ИГРАТЬ", "primary")
        self.play_btn.setBreathing(True)
        self.play_btn.setMinimumHeight(50)
        self.play_btn.setMinimumWidth(190)
        self.stop_btn = SunButton("■  СТОП", "danger")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.hide()
        row.addWidget(self.play_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        col.addLayout(row)
        self.state_lb = QLabel("Готов к работе.")
        self.state_lb.setObjectName("muted")
        col.addWidget(self.state_lb)
        hl.addLayout(col, 1)
        l.addWidget(hero)

        acts = QHBoxLayout()
        acts.setSpacing(10)
        self.act_new = SunButton("＋  Новый профиль", "ghost")
        self.act_mods = SunButton("◈  Добавить моды", "ghost")
        self.act_net = SunButton("⇄  Играть с другом", "ghost")
        for b in (self.act_new, self.act_mods, self.act_net):
            b.setMinimumHeight(44)
            acts.addWidget(b)
        l.addLayout(acts)

        tune = self.panel()
        tl = QGridLayout(tune)
        tl.setContentsMargins(20, 16, 20, 16)
        tl.setVerticalSpacing(8)
        cap = QLabel("ПАМЯТЬ ДЛЯ ИГРЫ")
        cap.setObjectName("tiny")
        tl.addWidget(cap, 0, 0, 1, 3)
        self.ram = QSlider(Qt.Horizontal)
        self.ram.setRange(1, 16)
        self.ram_val = QLabel("3 ГБ")
        self.ram_val.setObjectName("accent")
        self.ram_val.setMinimumWidth(60)
        tl.addWidget(self.ram, 1, 0, 1, 2)
        tl.addWidget(self.ram_val, 1, 2)
        hint = QLabel("Для сборок с модами обычно 4–6 ГБ.")
        hint.setObjectName("muted")
        tl.addWidget(hint, 2, 0, 1, 3)
        l.addWidget(tune)

        cap = QLabel("НЕДАВНО ИГРАЛИ")
        cap.setObjectName("tiny")
        l.addWidget(cap)
        self.recent_box = QWidget()
        self.recent_box.setObjectName("clear")
        self.recent_v = QVBoxLayout(self.recent_box)
        self.recent_v.setContentsMargins(0, 0, 0, 0)
        self.recent_v.setSpacing(6)
        self.recent_v.addStretch(1)
        l.addWidget(self.recent_box)
        l.addStretch(1)
        self._add("home", w)

    def _page_versions(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        bar = self.panel()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        self.vfilter = QComboBox()
        self.vfilter.addItems(["Релизы", "Снапшоты", "Beta", "Alpha", "Все"])
        self.vfilter.setMinimumWidth(120)
        self.vsearch = QLineEdit()
        self.vsearch.setPlaceholderText("Поиск версии…")
        self.vcount = QLabel("0")
        self.vcount.setObjectName("accent")
        bl.addWidget(self.vfilter)
        bl.addWidget(self.vsearch, 1)
        bl.addWidget(self.vcount)
        l.addWidget(bar)
        hint = QLabel("Двойной клик или ПКМ → создать профиль")
        hint.setObjectName("muted")
        l.addWidget(hint)
        self.vlist = QListWidget()
        self.vlist.setObjectName("list")
        self.vlist.setContextMenuPolicy(Qt.CustomContextMenu)
        l.addWidget(self.vlist, 1)
        self._add("versions", w)

    def _page_catalog(self, key):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        if key == "mods":
            self.mod_target = QLabel("Профиль не выбран")
            self.mod_target.setObjectName("muted")
            self.mod_target.setWordWrap(True)
            l.addWidget(self.mod_target)
        bar = self.panel()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        if key == "mods":
            self.mtype = QComboBox()
            self.mtype.addItems(list(P.TYPES))
            self.mtype.setMinimumWidth(120)
            bl.addWidget(self.mtype)
        q = QLineEdit()
        q.setPlaceholderText("Поиск на Modrinth…")
        setattr(self, f"{key}_q", q)
        go = SunButton("НАЙТИ", "primary")
        setattr(self, f"{key}_go", go)
        bl.addWidget(q, 1)
        bl.addWidget(go)
        if key == "packs":
            imp = SunButton("ИМПОРТ", "ghost")
            imp.clicked.connect(self._import_pack)
            bl.addWidget(imp)
        l.addWidget(bar)

        tree = QTreeWidget()
        tree.setObjectName("tree")
        tree.setColumnCount(3)
        tree.setHeaderLabels(["НАЗВАНИЕ", "ЗАГРУЗКИ", "ОПИСАНИЕ"])
        tree.setColumnWidth(0, 240)
        tree.setColumnWidth(1, 100)
        tree.setRootIsDecorated(False)
        setattr(self, f"{key}_tree", tree)
        l.addWidget(tree, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        inst = SunButton("УСТАНОВИТЬ", "primary")
        setattr(self, f"{key}_install", inst)
        row.addWidget(inst)
        if key == "mods":
            e4 = SunButton("⇄  УСТАНОВИТЬ e4mc (КООП)", "ghost")
            e4.clicked.connect(self._install_e4mc)
            row.addWidget(e4)
        row.addStretch(1)
        l.addLayout(row)
        self._add(key, w)

    def _page_profiles(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)
        bar = self.panel()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        self.pfilter = QLineEdit()
        self.pfilter.setPlaceholderText("Фильтр…")
        self.ploader = QComboBox()
        self.ploader.addItems(["Все загрузчики", "Ванилла", "Fabric", "Quilt", "Forge"])
        self.pcount = QLabel("0")
        self.pcount.setObjectName("accent")
        bl.addWidget(self.pfilter, 1)
        bl.addWidget(self.ploader)
        bl.addWidget(self.pcount)
        l.addWidget(bar)
        legend = QLabel("Клик — выбрать · двойной клик — играть · ПКМ — меню")
        legend.setObjectName("muted")
        l.addWidget(legend)
        self.pscroll = QScrollArea()
        self.pscroll.setObjectName("scroll")
        self.pscroll.setWidgetResizable(True)
        self.pscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        box = QWidget()
        box.setObjectName("clear")
        self.pv = QVBoxLayout(box)
        self.pv.setContentsMargins(0, 0, 12, 0)
        self.pv.setSpacing(8)
        self.pv.addStretch(1)
        self.pscroll.setWidget(box)
        l.addWidget(self.pscroll, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.p_play = SunButton("ИГРАТЬ", "primary")
        self.p_active = SunButton("АКТИВНЫМ", "ghost")
        self.p_view = SunButton("ЧТО ВНУТРИ", "ghost")
        self.p_mods = SunButton("МОДЫ", "ghost")
        self.p_icon = SunButton("АВАТАР", "ghost")
        self.p_folder = SunButton("ПАПКА", "ghost")
        self.p_del = SunButton("УДАЛИТЬ", "danger")
        for b in (self.p_play, self.p_active, self.p_view, self.p_mods,
                  self.p_icon, self.p_folder, self.p_del):
            row.addWidget(b)
        row.addStretch(1)
        l.addLayout(row)
        self._add("profiles", w)

    def _page_net(self):
        w, l = self._scroll()
        hero = self.panel(True)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(22, 20, 22, 20)
        hl.setSpacing(8)
        t = QLabel("ИГРАТЬ С ДРУГОМ")
        t.setObjectName("h1")
        hl.addWidget(t)
        d = QLabel("Два способа. Первый — открыть свой одиночный мир через мод e4mc. "
                   "Второй — поднять отдельный сервер (свой мир, живёт даже когда ты вышел).")
        d.setWordWrap(True)
        d.setObjectName("muted")
        hl.addWidget(d)
        l.addWidget(hero)

        p1 = self.panel()
        p1l = QVBoxLayout(p1)
        p1l.setContentsMargins(20, 16, 20, 16)
        p1l.setSpacing(8)
        cap = QLabel("СПОСОБ 1 · СВОЙ МИР ЧЕРЕЗ e4mc")
        cap.setObjectName("tiny")
        p1l.addWidget(cap)
        steps = QLabel("1. Профиль должен быть на Fabric или Quilt\n"
                       "2. Нажми кнопку ниже — мод установится\n"
                       "3. Запусти игру, открой мир, нажми «Открыть для сети»\n"
                       "4. В чате появится адрес — отправь другу\n"
                       "Другу ничего ставить не нужно, он вводит адрес в «Прямое подключение».")
        steps.setObjectName("muted")
        steps.setWordWrap(True)
        p1l.addWidget(steps)
        self.e4_btn = SunButton("УСТАНОВИТЬ e4mc В АКТИВНЫЙ ПРОФИЛЬ", "primary")
        self.e4_btn.clicked.connect(self._install_e4mc)
        p1l.addWidget(self.e4_btn)
        l.addWidget(p1)

        join = self.panel()
        jl = QVBoxLayout(join)
        jl.setContentsMargins(20, 16, 20, 16)
        jl.setSpacing(8)
        cap = QLabel("ПОДКЛЮЧИТЬСЯ К ДРУГУ")
        cap.setObjectName("tiny")
        jl.addWidget(cap)
        jr = QHBoxLayout()
        jr.setSpacing(8)
        self.addr = QLineEdit()
        self.addr.setPlaceholderText("адрес:порт от друга")
        self.j_go = SunButton("ЗАЙТИ", "primary")
        jr.addWidget(self.addr, 1)
        jr.addWidget(self.j_go)
        jl.addLayout(jr)
        l.addWidget(join)

        p2 = self.panel()
        p2l = QVBoxLayout(p2)
        p2l.setContentsMargins(20, 16, 20, 16)
        p2l.setSpacing(8)
        cap = QLabel("СПОСОБ 2 · ОТДЕЛЬНЫЙ СЕРВЕР")
        cap.setObjectName("tiny")
        p2l.addWidget(cap)
        note = QLabel("Создаётся НОВЫЙ пустой мир, отдельный от твоих одиночных. "
                      "Работает без IPv6 и проброса портов через туннель bore.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        p2l.addWidget(note)
        self.eula = QCheckBox("Принимаю Minecraft EULA (aka.ms/MinecraftEULA)")
        p2l.addWidget(self.eula)
        r = QHBoxLayout()
        r.setSpacing(8)
        self.relay = QLineEdit()
        self.relay.setPlaceholderText("bore.pub")
        self.h_start = SunButton("ЗАПУСТИТЬ", "primary")
        self.h_stop = SunButton("ОСТАНОВИТЬ", "danger")
        self.h_stop.setEnabled(False)
        r.addWidget(QLabel("Relay"))
        r.addWidget(self.relay, 1)
        r.addWidget(self.h_start)
        r.addWidget(self.h_stop)
        p2l.addLayout(r)
        self.host_state = QLabel("Сервер не запущен.")
        self.host_state.setObjectName("muted")
        self.host_state.setWordWrap(True)
        p2l.addWidget(self.host_state)
        self.public = QLineEdit()
        self.public.setReadOnly(True)
        self.public.setPlaceholderText("Адрес появится после запуска")
        p2l.addWidget(self.public)
        cp = SunButton("КОПИРОВАТЬ АДРЕС", "ghost")
        cp.clicked.connect(self._copy_addr)
        p2l.addWidget(cp)
        online_cap = QLabel("ОНЛАЙН")
        online_cap.setObjectName("tiny")
        p2l.addWidget(online_cap)
        self.online_row = QHBoxLayout()
        self.online_row.setSpacing(5)
        self.online_count = badge("0 ИГРОКОВ", T.DIM)
        self.online_row.addWidget(self.online_count)
        self.online_row.addStretch(1)
        p2l.addLayout(self.online_row)
        self.cmd = QLineEdit()
        self.cmd.setPlaceholderText("Команда сервера: say привет / op ник / list")
        p2l.addWidget(self.cmd)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(160)
        p2l.addWidget(self.console)
        l.addWidget(p2)
        l.addStretch(1)
        self._add("net", w)

    def _page_settings(self):
        w, il = self._scroll()
        acc = self.panel()
        al = QVBoxLayout(acc)
        al.setContentsMargins(20, 16, 20, 16)
        al.setSpacing(8)
        cap = QLabel("НИК")
        cap.setObjectName("tiny")
        al.addWidget(cap)
        nr = QHBoxLayout()
        nr.setSpacing(8)
        self.nick_edit = QLineEdit()
        self.nick_edit.setPlaceholderText("3–16 символов: латиница, цифры, _")
        self.nick_set = SunButton("ПРИМЕНИТЬ", "ghost")
        nr.addWidget(self.nick_edit, 1)
        nr.addWidget(self.nick_set)
        al.addLayout(nr)
        note = QLabel("Офлайн-ник, Microsoft-аккаунт не нужен. На серверах с "
                      "online-mode=true такой вход не пройдёт.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        al.addWidget(note)
        il.addWidget(acc)

        jvm = self.panel()
        jl = QVBoxLayout(jvm)
        jl.setContentsMargins(20, 16, 20, 16)
        jl.setSpacing(8)
        cap = QLabel("JVM АРГУМЕНТЫ")
        cap.setObjectName("tiny")
        jl.addWidget(cap)
        self.jvm = QPlainTextEdit()
        self.jvm.setFixedHeight(72)
        self.jvm.setPlaceholderText("Пусто = стандартные")
        jl.addWidget(self.jvm)
        preset = SunButton("🎮  ПРЕСЕТ G1GC", "ghost")
        preset.clicked.connect(self._preset)
        jl.addWidget(preset)
        il.addWidget(jvm)

        paths = self.panel()
        pl = QVBoxLayout(paths)
        pl.setContentsMargins(20, 16, 20, 16)
        pl.setSpacing(8)
        cap = QLabel("ПАПКИ")
        cap.setObjectName("tiny")
        pl.addWidget(cap)
        pr = QHBoxLayout()
        pr.setSpacing(8)
        for text, target in (("ПРОФИЛИ", P.INST), ("ОБЩИЕ ФАЙЛЫ", P.GAME),
                             ("СЕРВЕРЫ", P.SERVERS), ("ВСЁ", P.DATA)):
            b = SunButton(text, "ghost")
            b.clicked.connect(lambda _=False, t=target: P.open_path(t))
            pr.addWidget(b)
        pr.addStretch(1)
        pl.addLayout(pr)
        loc = QLabel(str(P.DATA))
        loc.setObjectName("muted")
        loc.setWordWrap(True)
        pl.addWidget(loc)
        il.addWidget(paths)

        logp = self.panel()
        ll = QVBoxLayout(logp)
        ll.setContentsMargins(20, 16, 20, 16)
        ll.setSpacing(8)
        cap = QLabel("ЖУРНАЛ")
        cap.setObjectName("tiny")
        ll.addWidget(cap)
        self.logview = QPlainTextEdit()
        self.logview.setReadOnly(True)
        self.logview.setFixedHeight(200)
        ll.addWidget(self.logview)
        il.addWidget(logp)
        il.addStretch(1)
        self._add("settings", w)

    def go(self, key):
        w = self.pages[key]
        self.stack.setCurrentWidget(w)
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        self._page_anim = QPropertyAnimation(eff, b"opacity", self)
        self._page_anim.setDuration(220)
        self._page_anim.setStartValue(0.0)
        self._page_anim.setEndValue(1.0)
        self._page_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._page_anim.start()
        for k, b in self.nav.items():
            b.setChecked(k == key)
        self.be.save({"page": key})
        if key == "mods":
            self._update_target()

    def _tb_press(self, e):
        if e.button() == Qt.LeftButton:
            h = self.windowHandle()
            if h:
                h.startSystemMove()
            e.accept()

    def _wire(self):
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close.clicked.connect(self.close)
        self.play_btn.clicked.connect(lambda: self.be.play())
        self.stop_btn.clicked.connect(self.be.stop_game)
        self.ram.valueChanged.connect(self._ram)
        self.act_new.clicked.connect(lambda: self._new_profile())
        self.act_mods.clicked.connect(lambda: self.go("mods"))
        self.act_net.clicked.connect(lambda: self.go("net"))

        self.vsearch.textChanged.connect(lambda _: self._timer.start())
        self.vfilter.currentIndexChanged.connect(self._render_versions)
        self.vlist.itemDoubleClicked.connect(lambda _: self._create_from_list())
        self.vlist.customContextMenuRequested.connect(self._version_menu)

        for key in ("mods", "packs"):
            getattr(self, f"{key}_go").clicked.connect(lambda _=False, k=key: self._search(k))
            getattr(self, f"{key}_q").returnPressed.connect(lambda k=key: self._search(k))
            getattr(self, f"{key}_install").clicked.connect(lambda _=False, k=key: self._install(k))
        self.mtype.currentIndexChanged.connect(self._update_target)

        self.pfilter.textChanged.connect(lambda _: self._render_profiles())
        self.ploader.currentIndexChanged.connect(self._render_profiles)
        self.p_play.clicked.connect(lambda: self._p_act("play"))
        self.p_active.clicked.connect(lambda: self._p_act("active"))
        self.p_view.clicked.connect(lambda: self._p_act("view"))
        self.p_mods.clicked.connect(lambda: self._p_act("mods"))
        self.p_icon.clicked.connect(lambda: self._p_act("icon"))
        self.p_folder.clicked.connect(lambda: self._p_act("folder"))
        self.p_del.clicked.connect(lambda: self._p_act("delete"))

        self.h_start.clicked.connect(self._host_start)
        self.h_stop.clicked.connect(self.host.stop)
        self.cmd.returnPressed.connect(self._send_cmd)
        self.j_go.clicked.connect(lambda: self.be.play(server=self.addr.text().strip()))

        self.nick_set.clicked.connect(self._set_nick)
        self.nick_edit.returnPressed.connect(self._set_nick)
        self.jvm.textChanged.connect(
            lambda: self.be.save({"jvm_extra": self.jvm.toPlainText()}))

    def _on_event(self, event, payload):
        if event == "toast":
            self._toast(*payload)
        elif event == "status":
            self.status_lb.setText(payload)
            self.state_lb.setText(payload)
        elif event == "progress":
            d, t = payload
            self.dock.show()
            self.bar.setMaximum(t)
            self.bar.setValue(d)
            self.task_pct.setText(f"{int(d * 100 / t)}%")
        elif event == "task":
            self.dock.show()
            self.task_title.setText(payload["title"])
            st = payload["state"]
            if st == "done":
                self.bar.setValue(self.bar.maximum())
                self.task_pct.setText("✓")
                QTimer.singleShot(1400, self.dock.hide)
            elif st == "error":
                self.task_pct.setText("✕")
                QTimer.singleShot(4500, self.dock.hide)
            else:
                self.task_pct.setText("…")
        elif event == "log":
            self.logview.appendPlainText(payload)
            if payload.startswith(("[server]", "[tunnel]")):
                self.console.appendPlainText(payload)
        elif event == "versions":
            self.versions = payload
            self._render_versions()
        elif event == "profiles":
            self.profiles = payload
            self._render_profiles()
            self._active(self.be.cfg.get("cur", ""))
        elif event == "game":
            self._game_state(payload)
        elif event == "nick":
            self.nick_label.setText(payload)
        elif event == "hits":
            key, hits = payload
            self.hits[key] = hits
            self._fill_tree(key, hits)
        elif event == "host":
            self._host_event(payload)

    def _game_state(self, st):
        if st == "preparing":
            self.play_btn.setEnabled(False)
            self.play_btn.setText("ГОТОВЛЮ…")
            self.stop_btn.hide()
        elif st == "running":
            self.play_btn.setEnabled(False)
            self.play_btn.setText("ЗАПУЩЕНО ✓")
            self.stop_btn.show()
        else:
            self.play_btn.setEnabled(bool(self.profiles))
            self.play_btn.setText("▶   ИГРАТЬ")
            self.stop_btn.hide()

    def _host_event(self, d):
        if d.get("state") == "on":
            self.h_start.setEnabled(False)
            self.h_stop.setEnabled(True)
            self.host_state.setText("Сервер запущен, готовлю туннель…")
            self.host_state.setStyleSheet(f"color:{T.WARN};")
        elif d.get("state") == "off":
            self.h_start.setEnabled(True)
            self.h_stop.setEnabled(False)
            self.public.clear()
            self.host_state.setText("Сервер не запущен.")
            self.host_state.setStyleSheet("")
        if d.get("address"):
            self.public.setText(d["address"])
            self.host_state.setText(f'✓ Работает · версия {d.get("mc","")}')
            self.host_state.setStyleSheet(f"color:{T.OK};")
        if "players" in d:
            self._render_online(d["players"])

    def _render_online(self, players):
        for b in self._online_badges:
            b.setParent(None)
            b.deleteLater()
        self._online_badges = []
        n = len(players)
        self.online_count.setText(f"{n} ИГРОК{'ОВ' if n != 1 else ''}")
        self.online_count.setStyleSheet(
            f"background:{T.OK}1f; color:{T.OK}; border:1px solid {T.OK}66;"
            f"padding:2px 8px; font-size:9px; font-weight:700;" if n else
            f"background:{T.DIM}1f; color:{T.DIM}; border:1px solid {T.DIM}66;"
            f"padding:2px 8px; font-size:9px; font-weight:700;")
        for name in players:
            b = badge(name, T.ACCENT_HI)
            self.online_row.insertWidget(self.online_row.count() - 1, b)
            self._online_badges.append(b)

    def _ram(self, v):
        self.ram_val.setText(f"{v} ГБ")
        self.be.save({"ram": v})

    def _set_nick(self):
        if self.be.set_nick(self.nick_edit.text()):
            self._toast("Ник сохранён", "success")
            self.nick_edit.clear()

    def _preset(self):
        self.jvm.setPlainText(
            "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 "
            "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC "
            "-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 "
            "-XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 "
            "-XX:InitiatingHeapOccupancyPercent=15 -Dfile.encoding=UTF-8")
        self.ram.setValue(6)
        self._toast("Пресет: 6 ГБ + G1GC", "success")

    def _new_profile(self, mc=None):
        dlg = CreateDialog(self, self.versions, mc or self.be.cfg.get("mc", ""))
        if dlg.exec() == QDialog.Accepted:
            name, m, loader, lv = dlg.data()
            self.be.create(name, m, loader, lv)

    def _create_from_list(self):
        it = self.vlist.currentItem()
        if it:
            self._new_profile(it.data(Qt.UserRole))

    def _version_menu(self, pos):
        it = self.vlist.itemAt(pos)
        if not it:
            return
        mc = it.data(Qt.UserRole)
        m = QMenu(self)
        a_new = m.addAction(f"Создать профиль · {mc}")
        m.addSeparator()
        quick = {}
        for ld in P.LOADERS:
            quick[m.addAction(f"Быстро: {P.LOADER_LABEL[ld]}")] = ld
        act = m.exec(self.vlist.mapToGlobal(pos))
        if act == a_new:
            self._new_profile(mc)
        elif act in quick:
            ld = quick[act]
            suffix = "" if ld == "vanilla" else " " + ld
            self.be.create(f"{mc}{suffix}", mc, ld)

    def _render_versions(self):
        t = ["release", "snapshot", "old_beta", "old_alpha", "all"][self.vfilter.currentIndex()]
        q = self.vsearch.text().strip().lower()
        self.vlist.setUpdatesEnabled(False)
        self.vlist.clear()
        n = 0
        for v in self.versions:
            if t != "all" and v["type"] != t:
                continue
            if q and q not in v["id"].lower():
                continue
            it = QListWidgetItem(f'{v["id"]:<24} {v["type"]:<12} '
                                 f'{v.get("releaseTime","")[:10]}')
            it.setData(Qt.UserRole, v["id"])
            self.vlist.addItem(it)
            n += 1
        self.vlist.setUpdatesEnabled(True)
        self.vcount.setText(str(n))

    def _update_target(self):
        n = self.be.cfg.get("cur")
        if n:
            m = P.read_meta(n)
            cnt = P.count_files(n, P.TYPES[self.mtype.currentText()])
            self.mod_target.setText(f'Установка в: {n}  ·  {m.get("mc")}  ·  '
                                    f'{m.get("loader","vanilla")}  ·  файлов: {cnt}')
            self.mod_target.setStyleSheet(f"color:{T.ACCENT_HI};")
        else:
            self.mod_target.setText("Профиль не выбран — выбери на «ПРОФИЛИ»")
            self.mod_target.setStyleSheet(f"color:{T.WARN};")

    def _search(self, key):
        q = getattr(self, f"{key}_q").text().strip()
        if key == "mods":
            ptype = P.TYPES[self.mtype.currentText()]
            n = self.be.cfg.get("cur")
            if not n:
                self._toast("Сначала выбери профиль", "warning")
                return
            m = P.read_meta(n)
            mc, loader = m.get("mc"), m.get("loader")
        else:
            ptype, mc, loader = "modpack", None, None

        def work():
            try:
                hits = catalog.search(q, ptype, mc, loader)
                self.bridge.emit_evt("hits", (key, hits))
                if not hits:
                    self._toast("Ничего не найдено", "warning")
            except Exception as e:
                self._toast(str(e), "error")
        self.be.status("Ищу на Modrinth…")
        threading.Thread(target=work, daemon=True).start()

    def _fill_tree(self, key, hits):
        tree = getattr(self, f"{key}_tree")
        tree.clear()
        for i, h in enumerate(hits):
            it = QTreeWidgetItem([h.get("title", "?"),
                                  f'{h.get("downloads",0):,}',
                                  h.get("description", "")])
            it.setData(0, Qt.UserRole, i)
            tree.addTopLevelItem(it)

    def _install(self, key):
        tree = getattr(self, f"{key}_tree")
        it = tree.currentItem()
        if not it:
            self._toast("Выбери элемент в списке", "warning")
            return
        hit = self.hits[key][it.data(0, Qt.UserRole)]
        if key == "packs":
            name = P.clean_name(hit.get("title", "pack"))

            def work():
                real = catalog.install_pack(hit["project_id"], name, self.be)
                self.be.save({"cur": real})
                self._toast(f"«{real}» установлена", "success")
            self.be.job("Установка сборки", work,
                        then=lambda: self.bridge.emit_evt("profiles", P.list_profiles()))
            return
        dlg = TargetDialog(self, hit)
        if dlg.exec() != QDialog.Accepted or not dlg.choice:
            return
        target = dlg.choice
        ptype = P.TYPES[self.mtype.currentText()]

        def work():
            catalog.install_item(hit["project_id"], ptype, target, self.be)
            self._toast("Установлено", "success")
        self.be.job("Установка", work, then=self._update_target)

    def _install_e4mc(self):
        n = self.be.cfg.get("cur")
        if not n:
            self._toast("Сначала выбери профиль", "warning")
            return

        def work():
            catalog.install_e4mc(n, self.be)
            self._toast("e4mc установлен — открой мир для сети в игре", "success")
        self.be.job("Установка e4mc", work, then=self._update_target)

    def _import_pack(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт", "", "Modrinth (*.mrpack *.zip)")
        if not path:
            return

        def work():
            real = catalog.import_mrpack(path, self.be)
            self.be.save({"cur": real})
            self._toast(f"Импортировано: {real}", "success")
        self.be.job("Импорт", work,
                    then=lambda: self.bridge.emit_evt("profiles", P.list_profiles()))

    def _clear(self, vbox):
        while vbox.count() > 1:
            item = vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_profiles(self):
        self._clear(self.pv)
        self._clear(self.recent_v)
        self.cards = {}
        self.recent_cards = {}
        q = self.pfilter.text().strip().lower()
        want = [None] + P.LOADERS
        wf = want[self.ploader.currentIndex()]
        active = self.be.cfg.get("cur", "")
        shown = 0
        for m in self.profiles:
            ld = m.get("loader", "vanilla")
            if wf and ld != wf:
                continue
            if q and q not in m["name"].lower() and q not in m.get("mc", "").lower():
                continue
            card = ProfileCard(m, P.count_files(m["name"]),
                               pixmap_or_default(m.get("icon"), 56))
            card.picked.connect(self._pick)
            card.play_req.connect(self._card_play)
            card.mods_req.connect(self._card_mods)
            card.menu_req.connect(self._profile_menu)
            card.set_active(m["name"] == active)
            card.set_selected(m["name"] == self.selected)
            self.cards[m["name"]] = card
            self.pv.insertWidget(self.pv.count() - 1, card)
            shown += 1
        if not shown:
            lb = QLabel("Ничего нет. Создай профиль на «ВЕРСИИ».")
            lb.setObjectName("muted")
            lb.setWordWrap(True)
            self.pv.insertWidget(0, lb)
        self.pcount.setText(str(shown))

        recent = [m for m in self.profiles if m.get("last_played")][:5]
        for m in recent:
            card = ProfileCard(m, P.count_files(m["name"]),
                               pixmap_or_default(m.get("icon"), 40), compact=True)
            card.picked.connect(self._card_play)
            card.play_req.connect(self._card_play)
            card.menu_req.connect(self._profile_menu)
            card.set_active(m["name"] == active)
            self.recent_cards[m["name"]] = card
            self.recent_v.insertWidget(self.recent_v.count() - 1, card)
        if not recent:
            lb = QLabel("Ещё ничего не запускали")
            lb.setObjectName("muted")
            self.recent_v.insertWidget(0, lb)

    def _pick(self, name):
        self.selected = name
        for k, c in self.cards.items():
            c.set_selected(k == name)

    def _card_play(self, name):
        self._pick(name)
        self.be.save({"cur": name})
        self._active(name)
        self.be.play(name)

    def _card_mods(self, name):
        self._pick(name)
        self.be.save({"cur": name})
        self._active(name)
        self.go("mods")

    def _active(self, name):
        m = next((x for x in self.profiles if x["name"] == name), None)
        self.hero_name.setText(m["name"] if m else "Профиль не выбран")
        while self.hero_chips.count():
            it = self.hero_chips.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if m:
            self.hero_chips.addWidget(badge(m.get("mc", "?"), "#a8977c"))
            ld = m.get("loader", "vanilla")
            txt = P.LOADER_LABEL.get(ld, ld.upper())
            if m.get("loader_version"):
                txt += " " + m["loader_version"]
            self.hero_chips.addWidget(badge(txt, P.LOADER_COLOR.get(ld, T.DIM)))
            cnt = P.count_files(name)
            if cnt:
                self.hero_chips.addWidget(badge(f"{cnt} ФАЙЛОВ", T.ACCENT_HI))
            self.hero_chips.addStretch(1)
            self.hero_meta.setText(f'Запуск: {human_when(m.get("last_played"))}')
        else:
            self.hero_chips.addStretch(1)
            self.hero_meta.setText("—")
        self.hero_icon.setPixmap(pixmap_or_default(m.get("icon") if m else None, 124))
        self.play_btn.setEnabled(bool(m))
        for k, c in self.cards.items():
            c.set_active(k == name)
        for k, c in self.recent_cards.items():
            c.set_active(k == name)
        self._update_target()

    def _profile_menu(self, name, gpos):
        self._pick(name)
        m = QMenu(self)
        a_play = m.addAction("Играть")
        a_act = m.addAction("Сделать активным")
        a_view = m.addAction("Что внутри")
        a_mods = m.addAction("Добавить моды")
        m.addSeparator()
        a_icon = m.addAction("Сменить аватар")
        a_fold = m.addAction("Открыть папку")
        a_del = m.addAction("Удалить")
        act = m.exec(gpos)
        if act == a_play:
            self._card_play(name)
        elif act == a_act:
            self.be.save({"cur": name})
            self._active(name)
        elif act == a_view:
            ContentsDialog(self, name).exec()
            self._render_profiles()
        elif act == a_mods:
            self._card_mods(name)
        elif act == a_icon:
            self._set_icon(name)
        elif act == a_fold:
            P.open_path(P.game_dir(name))
        elif act == a_del:
            self._confirm_delete(name)

    def _set_icon(self, name):
        path, _ = QFileDialog.getOpenFileName(self, "Аватар", "",
                                              "Изображения (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.be.set_icon(name, path)

    def _confirm_delete(self, name):
        cnt = P.count_files(name)
        extra = f"\nВнутри {cnt} файлов — тоже удалятся." if cnt else ""
        r = QMessageBox.question(self, "Удалить",
                                 f'Удалить «{name}» с мирами и модами?{extra}',
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            self.be.delete(name)

    def _p_act(self, act):
        n = self.selected
        if not n or n not in [m["name"] for m in self.profiles]:
            self._toast("Кликни по профилю", "warning")
            return
        if act == "play":
            self._card_play(n)
        elif act == "active":
            self.be.save({"cur": n})
            self._active(n)
            self._toast(f"«{n}» активный", "success")
        elif act == "view":
            ContentsDialog(self, n).exec()
            self._render_profiles()
        elif act == "mods":
            self._card_mods(n)
        elif act == "icon":
            self._set_icon(n)
        elif act == "folder":
            P.open_path(P.game_dir(n))
        elif act == "delete":
            self._confirm_delete(n)

    def _host_start(self):
        if not self.eula.isChecked():
            self._toast("Нужно принять EULA", "warning")
            return
        n = self.be.cfg.get("cur")
        if not n:
            self._toast("Выбери профиль — сервер возьмёт его версию", "warning")
            return
        mc = P.read_meta(n).get("mc")
        ram = max(1, int(self.be.cfg.get("ram", 3)))
        relay = self.relay.text().strip() or "bore.pub"
        self.be.save({"eula": True, "relay": relay})

        def work():
            self.host.start(mc, ram, relay)
        self.be.job("Запуск сервера", work)

    def _send_cmd(self):
        c = self.cmd.text().strip()
        if c and self.host.command(c):
            self.console.appendPlainText("> " + c)
            self.cmd.clear()

    def _copy_addr(self):
        t = self.public.text().strip()
        if not t:
            self._toast("Адреса ещё нет", "warning")
            return
        QApplication.clipboard().setText(t)
        self._toast("Скопировано", "success")

    def _toast(self, text, kind="info"):
        self.state_lb.setText(text)
        alive = []
        for t in self.toasts:
            try:
                if t.parent() is not None:
                    alive.append(t)
            except RuntimeError:
                pass
        self.toasts = alive
        t = Toast(self, text, kind)
        t.show()
        y = 64 + sum(x.height() + 8 for x in self.toasts)
        self.toasts.append(t)
        t.play(self.width() - t.width() - 22, y)

        def drop():
            if t in self.toasts:
                self.toasts.remove(t)
        QTimer.singleShot(4200, drop)

    def _load(self):
        c = self.be.cfg
        self.ram.setValue(int(c.get("ram", 3)))
        self._ram(int(c.get("ram", 3)))
        self.nick_label.setText(c.get("nick", "Player"))
        self.relay.setText(c.get("relay", "bore.pub"))
        self.eula.setChecked(bool(c.get("eula")))
        self.addr.setText(c.get("addr", ""))
        self.jvm.setPlainText(c.get("jvm_extra", ""))
        self.profiles = P.list_profiles()
        self._render_profiles()
        self._active(c.get("cur", ""))
        self.go(c.get("page", "home"))
        self.be.load_versions()
        if not c.get("cur") and self.profiles:
            played = [m for m in self.profiles if m.get("last_played")]
            if played:
                self.be.save({"cur": played[0]["name"]})
                self._active(played[0]["name"])

    def closeEvent(self, e):
        self.be.save({"addr": self.addr.text()})
        self.be.stop_game()
        self.host.stop()
        self._timer.stop()
        for w in self.findChildren(QWidget):
            tm = getattr(w, "_tm", None)
            if tm is not None:
                tm.stop()
        QApplication.processEvents()
        e.accept()