"""Диалоги."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QLineEdit, QComboBox, QListWidget,
                               QListWidgetItem, QMessageBox)

from sun import paths as P
from sun import backend as B
from sun import theme as T
from sun.widgets import SunButton, badge, human_when


class CreateDialog(QDialog):
    def __init__(self, parent, versions, default_mc=""):
        super().__init__(parent)
        self.setWindowTitle("Новый профиль")
        self.setMinimumWidth(500)
        if not versions:
            versions = B.fetch_versions()
        rel = [v["id"] for v in versions if v["type"] == "release"]

        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(24, 24, 24, 24)
        head = QLabel("Создание профиля")
        head.setObjectName("h1")
        lay.addWidget(head)

        form = QFormLayout()
        form.setSpacing(10)
        self.name = QLineEdit(f"Minecraft {default_mc}" if default_mc else "")
        self.mc = QComboBox()
        self.mc.addItems(rel)
        if default_mc in rel:
            self.mc.setCurrentText(default_mc)
        self.loader = QComboBox()
        for ld in P.LOADERS:
            self.loader.addItem(P.LOADER_LABEL[ld])
        self.lv = QLineEdit()
        self.lv.setPlaceholderText("Пусто = последняя подходящая")
        self.lv.setEnabled(False)
        form.addRow("Название", self.name)
        form.addRow("Версия игры", self.mc)
        form.addRow("Загрузчик", self.loader)
        form.addRow("Версия загрузчика", self.lv)
        lay.addLayout(form)

        self.hint = QLabel("Ванилла — просто игра, без модов.")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        if not rel:
            w = QLabel("⚠ Список версий пуст. Проверь интернет и перезапусти.")
            w.setStyleSheet(f"color:{T.ERR};")
            w.setWordWrap(True)
            lay.addWidget(w)

        btns = QHBoxLayout()
        cancel = SunButton("ОТМЕНА", "ghost")
        self.ok = SunButton("СОЗДАТЬ И СКАЧАТЬ", "primary")
        self.ok.setEnabled(bool(rel))
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        lay.addLayout(btns)
        self.ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.loader.currentIndexChanged.connect(self._hint)

    def _hint(self):
        ld = P.LOADERS[self.loader.currentIndex()]
        self.lv.setEnabled(ld != "vanilla")
        if ld == "vanilla":
            self.hint.setText("Ванилла — просто игра, без модов.")
        elif ld == "forge":
            self.hint.setText("Forge подберётся автоматически под версию игры.")
        else:
            self.hint.setText(f"{P.LOADER_LABEL[ld]} — нужен для большинства модов. "
                              f"Оставь версию пустой.")

    def data(self):
        ld = P.LOADERS[self.loader.currentIndex()]
        return (self.name.text().strip(), self.mc.currentText(),
                ld, self.lv.text().strip() or None)


class TargetDialog(QDialog):
    def __init__(self, parent, hit):
        super().__init__(parent)
        self.setWindowTitle("Куда установить")
        self.setMinimumWidth(520)
        self.choice = None
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 24, 24, 24)
        head = QLabel(hit.get("title", "?"))
        head.setObjectName("h1")
        lay.addWidget(head)
        d = QLabel(hit.get("description", ""))
        d.setObjectName("muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        self.lst = QListWidget()
        self.lst.setObjectName("list")
        lay.addWidget(self.lst, 1)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        btns = QHBoxLayout()
        cancel = SunButton("ОТМЕНА", "ghost")
        self.ok = SunButton("УСТАНОВИТЬ", "primary")
        self.ok.setEnabled(False)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(self.ok)
        lay.addLayout(btns)
        self.ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self.lst.currentItemChanged.connect(self._sel)
        for p in P.list_profiles():
            n = P.count_files(p["name"])
            extra = f"  ·  {n} файлов" if n else ""
            it = QListWidgetItem(f'{p["name"]}   ·   {p.get("mc","?")}   ·   '
                                 f'{p.get("loader","vanilla")}{extra}')
            it.setData(Qt.UserRole, p["name"])
            self.lst.addItem(it)
        if not self.lst.count():
            it = QListWidgetItem("Нет профилей — создай один")
            it.setFlags(Qt.NoItemFlags)
            self.lst.addItem(it)

    def _sel(self, cur, prev):
        if not cur or cur.data(Qt.UserRole) is None:
            self.ok.setEnabled(False)
            self.info.setText("")
            return
        self.choice = cur.data(Qt.UserRole)
        m = P.read_meta(self.choice)
        self.ok.setEnabled(True)
        self.info.setText(f'Подберём под {m.get("mc")} + {m.get("loader","vanilla")}')
        self.info.setStyleSheet(f"color:{T.OK};")


class ContentsDialog(QDialog):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.setWindowTitle("Содержимое профиля")
        self.setMinimumSize(560, 500)
        self.name = name
        m = P.read_meta(name)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(24, 24, 24, 24)
        head = QLabel(name)
        head.setObjectName("h1")
        lay.addWidget(head)
        chips = QHBoxLayout()
        chips.setSpacing(5)
        chips.addWidget(badge(m.get("mc", "?"), "#a8977c"))
        ld = m.get("loader", "vanilla")
        chips.addWidget(badge(P.LOADER_LABEL.get(ld, ld.upper()),
                              P.LOADER_COLOR.get(ld, T.DIM)))
        chips.addStretch(1)
        lay.addLayout(chips)
        info = QLabel(f'Загрузчик: {m.get("loader_version") or "авто"}  ·  '
                      f'Запуск: {human_when(m.get("last_played"))}')
        info.setObjectName("muted")
        lay.addWidget(info)
        self.kind = QComboBox()
        self.kind.addItems(list(P.TYPES))
        lay.addWidget(self.kind)
        self.files = QListWidget()
        self.files.setObjectName("list")
        lay.addWidget(self.files, 1)
        btns = QHBoxLayout()
        rm = SunButton("УДАЛИТЬ ФАЙЛ", "danger")
        folder = SunButton("ОТКРЫТЬ ПАПКУ", "ghost")
        close = SunButton("ЗАКРЫТЬ", "primary")
        btns.addWidget(rm)
        btns.addWidget(folder)
        btns.addStretch()
        btns.addWidget(close)
        lay.addLayout(btns)
        rm.clicked.connect(self._rm)
        folder.clicked.connect(lambda: P.open_path(P.game_dir(name)))
        close.clicked.connect(self.accept)
        self.kind.currentIndexChanged.connect(self._fill)
        self._fill()

    def _fill(self):
        self.files.clear()
        fs = P.list_files(self.name, P.TYPES[self.kind.currentText()])
        for f in fs:
            self.files.addItem(f)
        if not fs:
            it = QListWidgetItem("Пусто")
            it.setFlags(Qt.NoItemFlags)
            self.files.addItem(it)

    def _rm(self):
        it = self.files.currentItem()
        if not it or not (it.flags() & Qt.ItemIsSelectable):
            return
        kind = P.TYPES[self.kind.currentText()]
        path = P.game_dir(self.name) / P.FOLDERS[kind] / it.text()
        r = QMessageBox.question(self, "Удалить", f"Удалить {it.text()}?",
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                QMessageBox.warning(self, "Ошибка", str(e))
            self._fill()