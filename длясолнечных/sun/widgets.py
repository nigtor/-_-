"""Анимированные виджеты."""
import math
import random
import time
from pathlib import Path

from PySide6.QtCore import (Qt, Signal, QTimer, QPropertyAnimation, Property,
                            QEasingCurve, QPointF, QParallelAnimationGroup, QPoint)
from PySide6.QtGui import (QPainter, QColor, QLinearGradient, QRadialGradient,
                           QPen, QPixmap, QPainterPath)
from PySide6.QtWidgets import (QPushButton, QFrame, QWidget, QLabel, QProgressBar,
                               QGraphicsOpacityEffect, QVBoxLayout, QHBoxLayout,
                               QSizePolicy)

from sun import theme as T
from sun import paths as P


def human_when(ts):
    if not ts:
        return "не запускался"
    dt = time.time() - ts
    if dt < 60:
        return "только что"
    if dt < 3600:
        return f"{int(dt // 60)} мин назад"
    if dt < 86400:
        return f"{int(dt // 3600)} ч назад"
    if dt < 172800:
        return "вчера"
    if dt < 604800:
        return f"{int(dt // 86400)} дн назад"
    return time.strftime("%d.%m.%Y", time.localtime(ts))


def badge(text, color, solid=False):
    lb = QLabel(text)
    if solid:
        lb.setStyleSheet(f"background:{color}; color:#1a1206; border:none; border-radius:5px;"
                         f"padding:3px 9px; font-size:9px; font-weight:800; letter-spacing:0.5px;")
    else:
        lb.setStyleSheet(f"background:{color}1f; color:{color}; border:1px solid {color}66;"
                         f"border-radius:5px; padding:3px 9px; font-size:9px; font-weight:700;")
    lb.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
    return lb


def pixmap_or_default(path, size):
    pm = QPixmap()
    if path and Path(path).exists():
        pm.load(str(path))
    if pm.isNull():
        pm = QPixmap(size, size)
        pm.fill(QColor("#140e07"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(T.ACCENT))
        f = p.font()
        f.setPointSize(max(9, size // 3))
        f.setBold(True)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "☀")
        p.end()
    pm = pm.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    return _round_corners(pm, size, int(size * 0.22))


def _round_corners(pm, size, radius):
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(path)
    x = (pm.width() - size) // 2
    y = (pm.height() - size) // 2
    p.drawPixmap(-x, -y, pm)
    p.end()
    return out


class SunButton(QPushButton):
    def __init__(self, text, kind="normal"):
        super().__init__(text)
        self._kind = kind
        self._glow = 0.0
        self._pulse = 0.0
        self._breath = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)
        self._anim = QPropertyAnimation(self, b"glow")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._tick)

    def setBreathing(self, on):
        self._breath = on
        if on and not self._tm.isActive():
            self._tm.start(50)
        elif not on:
            self._tm.stop()
        self.update()

    def _tick(self):
        if not self._breath or not self.isEnabled():
            return
        w = self.window()
        if w and w.isMinimized():
            return
        self._pulse += 0.04
        self.update()

    def _g(self):
        return self._glow

    def _s(self, v):
        self._glow = v
        self.update()
    glow = Property(float, _g, _s)

    def enterEvent(self, e):
        if self.isEnabled():
            self._anim.stop()
            self._anim.setEndValue(1.0)
            self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        on = self.isEnabled()
        g = self._glow if on else 0.0
        if self._kind == "primary":
            br = 0.5 + 0.5 * math.sin(self._pulse) if (self._breath and on) else 0.0
            base = QColor(120 + int(50*g + 22*br), 62 + int(30*g + 14*br), 8 + int(12*g))
            edge = QColor(T.ACCENT_HI)
        elif self._kind == "danger":
            base = QColor(70 + int(30*g), 24, 24)
            edge = QColor(T.ERR)
        elif self._kind == "ghost":
            base = QColor(21 + int(18*g), 16 + int(14*g), 9 + int(8*g))
            edge = QColor(T.BORDER_HI)
        else:
            base = QColor(26 + int(20*g), 20 + int(16*g), 12 + int(10*g))
            edge = QColor(T.BORDER_HI)
        if not on:
            base = QColor("#14100a")
            edge = QColor("#241c12")
        p.setRenderHint(QPainter.Antialiasing)
        radius = 7.0
        p.setPen(Qt.NoPen)
        p.setBrush(base)
        p.drawRoundedRect(0, 0, w, h, radius, radius)
        p.setPen(QPen(edge if (g > 0.05 or self._kind == "primary") else QColor(T.BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(0.5, 0.5, w - 1, h - 1, radius, radius)
        if self.isDown():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 70))
            p.drawRoundedRect(0, 0, w, h, radius, radius)
        p.setPen(QColor("#fff5e6") if on else QColor("#5a4d3a"))
        f = p.font()
        f.setBold(True)
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


class Panel(QFrame):
    def __init__(self, accent=False):
        super().__init__()
        self.setObjectName("hero" if accent else "panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._glow = 0.0
        self._anim = QPropertyAnimation(self, b"glow")
        self._anim.setDuration(200)

    def _g(self):
        return self._glow

    def _s(self, v):
        self._glow = v
        self.update()
    glow = Property(float, _g, _s)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._glow > 0.02:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor(217, 119, 6, int(130 * self._glow)), 1.4))
            p.setBrush(Qt.NoBrush)
            r = 11.0 if self.objectName() == "hero" else 9.5
            p.drawRoundedRect(0.5, 0.5, self.width() - 1, self.height() - 1, r, r)
            p.end()


class SunLogo(QWidget):
    def __init__(self, size=72, pad=30):
        super().__init__()
        self.setFixedSize(size + pad, size + pad)
        self.s = size
        self.t = 0.0
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._tick)
        self._tm.start(33)

    def _tick(self):
        w = self.window()
        if self.isVisible() and not (w and w.isMinimized()):
            self.t += 0.028
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.s
        cx = self.width() / 2
        cy = self.height() / 2 + math.sin(self.t * 0.9) * (s * 0.03)
        pulse = 0.5 + 0.5 * math.sin(self.t * 1.5)
        spin = self.t * 0.35

        halo = QRadialGradient(cx, cy, s * 0.95)
        halo.setColorAt(0.0, QColor(245, 158, 11, int(46 + 40 * pulse)))
        halo.setColorAt(0.45, QColor(217, 119, 6, 22))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), s * 0.95, s * 0.95)

        for i in range(12):
            a = spin + i * (2 * math.pi / 12)
            ln = s * (0.30 + 0.10 * math.sin(self.t * 2 + i))
            r0 = s * 0.26
            alpha = int(90 + 90 * (0.5 + 0.5 * math.sin(self.t * 2 + i * 0.7)))
            p.setPen(QPen(QColor(251, 191, 36, alpha), max(1.0, s * 0.022)))
            p.drawLine(QPointF(cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                       QPointF(cx + math.cos(a) * (r0 + ln), cy + math.sin(a) * (r0 + ln)))

        r = s * 0.24
        disc = QRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 1.6)
        disc.setColorAt(0.0, QColor(255, 245, 214))
        disc.setColorAt(0.35, QColor(251, 191, 36))
        disc.setColorAt(0.75, QColor(217, 119, 6))
        disc.setColorAt(1.0, QColor(146, 64, 14))
        p.setPen(Qt.NoPen)
        p.setBrush(disc)
        p.drawEllipse(QPointF(cx, cy), r, r)

        cr = r * (0.34 + 0.14 * pulse)
        core = QRadialGradient(cx, cy, cr * 2.2)
        core.setColorAt(0.0, QColor(255, 255, 240, int(210 + 45 * pulse)))
        core.setColorAt(0.5, QColor(253, 224, 71, int(130 * pulse)))
        core.setColorAt(1.0, QColor(245, 158, 11, 0))
        p.setBrush(core)
        p.drawEllipse(QPointF(cx, cy), cr * 2.2, cr * 2.2)

        for i in range(4):
            a = -spin * 1.7 + i * (math.pi / 2)
            front = math.sin(a) >= 0
            sz = s * (0.030 if front else 0.020)
            p.setBrush(QColor(253, 224, 71, 210 if front else 80))
            p.drawEllipse(QPointF(cx + math.cos(a) * s * 0.60,
                                  cy + math.sin(a) * s * 0.25), sz, sz)
        p.end()


class SunCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.stars = [(random.random(), random.random(), random.random() * 1.1 + .3,
                       random.random() * 6.28) for _ in range(80)]
        self.embers = [(random.random(), random.random(), random.random() * 0.5 + 0.2,
                        random.random() * 6.28) for _ in range(22)]
        self.shoot = None
        self.t = 0.0
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._tick)
        self._tm.start(40)

    def _tick(self):
        w = self.window()
        if not self.isVisible() or (w and w.isMinimized()):
            return
        self.t += 0.022
        if self.shoot is None and random.random() < 0.003:
            self.shoot = [random.random() * .6 + .2, random.random() * .25, 0.0]
        if self.shoot:
            self.shoot[2] += 0.028
            if self.shoot[2] > 1:
                self.shoot = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(T.BG_DEEP))
        g.setColorAt(1, QColor("#050403"))
        p.fillRect(self.rect(), g)
        for cx, cy, rr, col in [(.16, .04, .60, QColor(146, 64, 14, 30)),
                                (.90, .92, .55, QColor(217, 119, 6, 16))]:
            rg = QRadialGradient(cx * w, cy * h, rr * max(w, h))
            rg.setColorAt(0, col)
            rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), rg)
        p.setPen(QPen(QColor(255, 220, 160, 4), 1))
        for x in range(0, w, 44):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 44):
            p.drawLine(0, y, w, y)
        for x, y, s, ph in self.stars:
            a = int(30 + 70 * (0.5 + 0.5 * math.sin(self.t * 1.2 + ph)))
            p.setPen(QPen(QColor(255, 236, 200, a), s))
            p.drawPoint(int(x * w), int(y * h))
        p.setPen(Qt.NoPen)
        for x, y, sp, ph in self.embers:
            yy = (y - self.t * sp * 0.05) % 1.0
            xx = x + math.sin(self.t * 0.7 + ph) * 0.012
            a = int(50 + 90 * (0.5 + 0.5 * math.sin(self.t * 2 + ph)))
            p.setBrush(QColor(251, 191, 36, a))
            p.drawEllipse(QPointF(xx * w, yy * h), 1.3, 1.3)
        if self.shoot:
            sx, sy, pr = self.shoot
            x0, y0 = sx * w, sy * h
            x1, y1 = x0 + pr * 230, y0 + pr * 130
            p.setPen(QPen(QColor(255, 226, 170, int(160 * (1 - pr))), 1.4))
            p.drawLine(int(x0 + (x1-x0)*.75), int(y0 + (y1-y0)*.75), int(x1), int(y1))
        p.end()


class ShimmerProgress(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self.setFixedHeight(6)
        self._t = 0
        self._tm = QTimer(self)
        self._tm.timeout.connect(self._tick)
        self._tm.start(50)

    def _tick(self):
        if self.isVisible():
            self._t += 6
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor("#120d07"))
        fw = int(w * self.value() / max(1, self.maximum()))
        if fw > 1:
            g = QLinearGradient(0, 0, fw, 0)
            g.setColorAt(0, QColor(T.ACCENT_LO))
            g.setColorAt(0.6, QColor(T.ACCENT))
            g.setColorAt(1, QColor(T.ACCENT_HI))
            p.fillRect(0, 0, fw, h, g)
            x = self._t % max(fw, 1)
            p.fillRect(x, 0, min(20, max(0, fw - x)), h, QColor(255, 240, 200, 55))
        p.end()


class Toast(QLabel):
    def __init__(self, parent, text, kind="info"):
        super().__init__(parent)
        self.setText(text)
        self.setWordWrap(True)
        col = {"success": T.OK, "error": T.ERR, "warning": T.WARN}.get(kind, T.ACCENT_HI)
        self.setStyleSheet(f"background:{T.PANEL_HI}; border:1px solid {col}; "
                           f"border-left:3px solid {col}; border-radius:8px; color:{T.TEXT}; "
                           f"padding:10px 14px; font-size:12px;")
        self.setMaximumWidth(360)
        self.adjustSize()
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.eff.setOpacity(0)

    def play(self, x, y):
        self.move(x + 34, y)
        self.fade = QPropertyAnimation(self.eff, b"opacity", self)
        self.fade.setDuration(220)
        self.fade.setStartValue(0)
        self.fade.setEndValue(1)
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setDuration(280)
        self.slide.setStartValue(QPoint(x + 34, y))
        self.slide.setEndValue(QPoint(x, y))
        self.slide.setEasingCurve(QEasingCurve.OutCubic)
        self.grp = QParallelAnimationGroup(self)
        self.grp.addAnimation(self.fade)
        self.grp.addAnimation(self.slide)
        self.grp.start()
        QTimer.singleShot(3600, self._out)

    def _out(self):
        self.f2 = QPropertyAnimation(self.eff, b"opacity", self)
        self.f2.setDuration(280)
        self.f2.setStartValue(1)
        self.f2.setEndValue(0)
        self.f2.finished.connect(self.deleteLater)
        self.f2.start()


class ProfileCard(Panel):
    picked = Signal(str)
    play_req = Signal(str)
    mods_req = Signal(str)
    menu_req = Signal(str, QPoint)

    def __init__(self, meta, mods_count, pixmap, compact=False):
        super().__init__()
        self.name = meta["name"]
        self._selected = False
        self._active = False
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pt: self.menu_req.emit(self.name, self.mapToGlobal(pt)))

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(12)
        ico = QLabel()
        sz = 40 if compact else 56
        ico.setFixedSize(sz, sz)
        ico.setObjectName("avatar")
        ico.setPixmap(pixmap)
        ico.setAlignment(Qt.AlignCenter)
        root.addWidget(ico)

        col = QVBoxLayout()
        col.setSpacing(5)
        top = QHBoxLayout()
        top.setSpacing(8)
        nm = QLabel(meta["name"])
        nm.setObjectName("cardname")
        top.addWidget(nm)
        self.mark = badge("АКТИВЕН", T.ACCENT_HI, solid=True)
        self.mark.hide()
        top.addWidget(self.mark)
        top.addStretch(1)
        col.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(5)
        chips.addWidget(badge(meta.get("mc", "?"), "#a8977c"))
        ld = meta.get("loader", "vanilla")
        txt = P.LOADER_LABEL.get(ld, ld.upper())
        lv = meta.get("loader_version")
        if lv and ld != "vanilla":
            txt += " " + (lv if len(lv) <= 12 else lv[:11] + "…")
        chips.addWidget(badge(txt, P.LOADER_COLOR.get(ld, T.DIM)))
        if mods_count:
            chips.addWidget(badge(f"{mods_count} ФАЙЛ.", T.ACCENT_HI))
        if meta.get("source") == "modrinth":
            chips.addWidget(badge("MODRINTH", "#1bd96a"))
        chips.addStretch(1)
        col.addLayout(chips)

        if not compact:
            info = QLabel(f'Запуск: {human_when(meta.get("last_played"))}')
            info.setObjectName("muted")
            col.addWidget(info)
        root.addLayout(col, 1)

        if not compact:
            acts = QVBoxLayout()
            acts.setSpacing(4)
            bp = SunButton("ИГРАТЬ", "primary")
            bp.setFixedSize(104, 30)
            bp.clicked.connect(lambda: self.play_req.emit(self.name))
            bm = SunButton("МОДЫ", "ghost")
            bm.setFixedSize(104, 26)
            bm.clicked.connect(lambda: self.mods_req.emit(self.name))
            acts.addWidget(bp)
            acts.addWidget(bm)
            root.addLayout(acts)

    def set_selected(self, v):
        self._selected = v
        self._restyle()

    def set_active(self, v):
        self._active = v
        self.mark.setVisible(v)
        self._restyle()

    def _restyle(self):
        if self._selected:
            self.setStyleSheet(f"#card {{ background:{T.PANEL_HI}; border-radius:10px; "
                               f"border:1px solid {T.ACCENT_HI}; "
                               f"border-left:3px solid {T.ACCENT_HI}; }}")
        elif self._active:
            self.setStyleSheet(f"#card {{ background:{T.PANEL_HI}; border-radius:10px; "
                               f"border:1px solid {T.BORDER_HI}; "
                               f"border-left:3px solid {T.ACCENT}; }}")
        else:
            self.setStyleSheet(f"#card {{ background:{T.PANEL}; border-radius:10px; "
                               f"border:1px solid {T.BORDER}; }}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.picked.emit(self.name)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.play_req.emit(self.name)
        super().mouseDoubleClickEvent(e)