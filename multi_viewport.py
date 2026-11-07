# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Multi-Viewport & View Tools Plugin for IngeTrazo.

Features:
- Multiple Viewports: Quad View (Top, Front, Right, Perspective), Split Horizontal, Split Vertical, Single View.
- Real-time Scene & History Synchronization across all viewports and multi-document project tabs (IngeTrazo 0.6+).
- Interactive Viewport Headers: quick view switcher, style switcher, and maximize/restore.
- Full Toolbar Suite:
  * Visibility Toolbar: Hide Selected (Ctrl+H), Unhide All (Ctrl+Shift+H), Unhide Last (Ctrl+Alt+H), Isolate (Ctrl+I).
  * Display Styles Toolbar: Wireframe (F2), Hidden Line (F3), Shaded (F4), Textures (F5), Monochrome (F6), X-Ray (F7), Toggle Edges.
  * Viewports & Views Toolbar: Single View, Quad View (Alt+W / Ctrl+Alt+Q), Split H, Split V, Standard Views (Ctrl+1..7), Projection (Shift+P), Zoom Extents (Shift+Z).
- Keyboard Shortcuts seamlessly hooked to IngeTrazo window.
"""
from __future__ import annotations

import math
import sys
import traceback
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QVector3D,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import core.style
from core.i18n import tr
from views.viewport import Viewport

# Theme Colors
ACCENT_COLOR = "#f2722b"  # IngeTrazo brand orange
BORDER_INACTIVE = "#333333"
BG_HEADER = "#252526"
BG_HEADER_ACTIVE = "#38281e"
TEXT_COLOR = "#e0e0e0"


# ---------------------------------------------------------------------------
# Vector Icon Generation
# ---------------------------------------------------------------------------

class IconVault:
    """Generates crisp vector icons for toolbars using QPainter."""

    @staticmethod
    def _create_pixmap(size: int = 24) -> tuple[QPixmap, QPainter]:
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        return pix, p

    @classmethod
    def hide_selected(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        pen = QPen(QColor(TEXT_COLOR), 1.6)
        p.setPen(pen)
        # Eye outline
        path = QPainterPath()
        path.moveTo(3, 12)
        path.cubicTo(7, 6, 17, 6, 21, 12)
        path.cubicTo(17, 18, 7, 18, 3, 12)
        p.strokePath(path, pen)
        # Diagonal slash
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.8))
        p.drawLine(QPointF(4, 20), QPointF(20, 4))
        p.end()
        return QIcon(pix)

    @classmethod
    def unhide_all(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        pen = QPen(QColor(TEXT_COLOR), 1.6)
        p.setPen(pen)
        # Eye outline
        path = QPainterPath()
        path.moveTo(3, 12)
        path.cubicTo(7, 6, 17, 6, 21, 12)
        path.cubicTo(17, 18, 7, 18, 3, 12)
        p.strokePath(path, pen)
        # Iris
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(ACCENT_COLOR)))
        p.drawEllipse(QPointF(12, 12), 3.2, 3.2)
        p.end()
        return QIcon(pix)

    @classmethod
    def unhide_last(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        pen = QPen(QColor(TEXT_COLOR), 1.6)
        p.setPen(pen)
        path = QPainterPath()
        path.moveTo(3, 12)
        path.cubicTo(7, 6, 17, 6, 21, 12)
        path.cubicTo(17, 18, 7, 18, 3, 12)
        p.strokePath(path, pen)
        # Return / Undo arrow at bottom-right
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.5))
        p.drawArc(QRectF(13, 11, 8, 8), 0 * 16, 270 * 16)
        p.drawLine(QPointF(17, 11), QPointF(15, 13))
        p.end()
        return QIcon(pix)

    @classmethod
    def isolate_selection(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        # Dotted outer frame
        p.setPen(QPen(QColor("#777777"), 1.2, Qt.DashLine))
        p.drawRect(QRectF(2, 2, 20, 20))
        # Solid central cube
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.6))
        p.setBrush(QBrush(QColor(ACCENT_COLOR).lighter(120)))
        p.drawRect(QRectF(7, 7, 10, 10))
        p.end()
        return QIcon(pix)

    @classmethod
    def wireframe(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(TEXT_COLOR), 1.4))
        # 3D isometric cube wireframe
        top = QPainterPath()
        top.moveTo(12, 3)
        top.lineTo(20, 7)
        top.lineTo(12, 11)
        top.lineTo(4, 7)
        top.closeSubpath()
        p.drawPath(top)
        p.drawLine(4, 7, 4, 17)
        p.drawLine(20, 7, 20, 17)
        p.drawLine(12, 11, 12, 21)
        p.drawLine(4, 17, 12, 21)
        p.drawLine(20, 17, 12, 21)
        p.end()
        return QIcon(pix)

    @classmethod
    def hidden_line(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor("#222222"), 1.4))
        p.setBrush(QBrush(QColor("#ffffff")))
        top = QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(12, 11), QPointF(4, 7)])
        left = QPolygonF([QPointF(4, 7), QPointF(12, 11), QPointF(12, 21), QPointF(4, 17)])
        right = QPolygonF([QPointF(20, 7), QPointF(12, 11), QPointF(12, 21), QPointF(20, 17)])
        p.drawPolygon(top)
        p.drawPolygon(left)
        p.drawPolygon(right)
        p.end()
        return QIcon(pix)

    @classmethod
    def shaded(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor("#111111"), 1.0))
        p.setBrush(QBrush(QColor("#e0e0e0")))
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(12, 11), QPointF(4, 7)]))
        p.setBrush(QBrush(QColor("#a8a8a8")))
        p.drawPolygon(QPolygonF([QPointF(4, 7), QPointF(12, 11), QPointF(12, 21), QPointF(4, 17)]))
        p.setBrush(QBrush(QColor("#707070")))
        p.drawPolygon(QPolygonF([QPointF(20, 7), QPointF(12, 11), QPointF(12, 21), QPointF(20, 17)]))
        p.end()
        return QIcon(pix)

    @classmethod
    def textures(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor("#111111"), 1.0))
        p.setBrush(QBrush(QColor(ACCENT_COLOR)))
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(12, 11), QPointF(4, 7)]))
        p.setBrush(QBrush(QColor(ACCENT_COLOR).darker(140)))
        p.drawPolygon(QPolygonF([QPointF(4, 7), QPointF(12, 11), QPointF(12, 21), QPointF(4, 17)]))
        p.setBrush(QBrush(QColor(ACCENT_COLOR).darker(180)))
        p.drawPolygon(QPolygonF([QPointF(20, 7), QPointF(12, 11), QPointF(12, 21), QPointF(20, 17)]))
        p.setPen(QPen(QColor("#ffffff"), 0.8))
        p.drawLine(QPointF(7, 12), QPointF(10, 14))
        p.drawLine(QPointF(5, 15), QPointF(11, 18))
        p.end()
        return QIcon(pix)

    @classmethod
    def monochrome(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor("#333333"), 1.0))
        p.setBrush(QBrush(QColor("#d0d0d0")))
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(12, 11), QPointF(4, 7)]))
        p.drawPolygon(QPolygonF([QPointF(4, 7), QPointF(12, 11), QPointF(12, 21), QPointF(4, 17)]))
        p.drawPolygon(QPolygonF([QPointF(20, 7), QPointF(12, 11), QPointF(12, 21), QPointF(20, 17)]))
        p.end()
        return QIcon(pix)

    @classmethod
    def xray(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.2))
        p.setBrush(QBrush(QColor(242, 114, 43, 70)))
        p.drawPolygon(QPolygonF([QPointF(12, 3), QPointF(20, 7), QPointF(12, 11), QPointF(4, 7)]))
        p.drawPolygon(QPolygonF([QPointF(4, 7), QPointF(12, 11), QPointF(12, 21), QPointF(4, 17)]))
        p.drawPolygon(QPolygonF([QPointF(20, 7), QPointF(12, 11), QPointF(12, 21), QPointF(20, 17)]))
        p.setPen(QPen(QColor("#ffffff"), 1.0, Qt.DotLine))
        p.drawLine(12, 3, 12, 13)
        p.drawLine(4, 17, 12, 13)
        p.drawLine(20, 17, 12, 13)
        p.end()
        return QIcon(pix)

    @classmethod
    def toggle_edges(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(ACCENT_COLOR), 2.2))
        p.drawRect(QRectF(4, 4, 16, 16))
        p.setPen(QPen(QColor(TEXT_COLOR), 1.2))
        p.drawLine(4, 12, 20, 12)
        p.drawLine(12, 4, 12, 20)
        p.end()
        return QIcon(pix)

    @classmethod
    def view_single(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.8))
        p.setBrush(QBrush(QColor(ACCENT_COLOR).darker(250)))
        p.drawRect(QRectF(3, 3, 18, 18))
        p.end()
        return QIcon(pix)

    @classmethod
    def view_quad(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(TEXT_COLOR), 1.2))
        p.drawRect(QRectF(3, 3, 8, 8))
        p.drawRect(QRectF(13, 13, 8, 8))
        p.drawRect(QRectF(3, 13, 8, 8))
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.5))
        p.setBrush(QBrush(QColor(ACCENT_COLOR).darker(180)))
        p.drawRect(QRectF(13, 3, 8, 8))
        p.end()
        return QIcon(pix)

    @classmethod
    def view_split_h(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(TEXT_COLOR), 1.2))
        p.drawRect(QRectF(3, 3, 18, 8))
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.5))
        p.drawRect(QRectF(3, 13, 18, 8))
        p.end()
        return QIcon(pix)

    @classmethod
    def view_split_v(cls) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor(TEXT_COLOR), 1.2))
        p.drawRect(QRectF(3, 3, 8, 18))
        p.setPen(QPen(QColor(ACCENT_COLOR), 1.5))
        p.drawRect(QRectF(13, 3, 8, 18))
        p.end()
        return QIcon(pix)

    @classmethod
    def standard_view(cls, view_type: str) -> QIcon:
        pix, p = cls._create_pixmap()
        p.setPen(QPen(QColor("#222222"), 1.0))
        top_poly = QPolygonF([QPointF(12, 4), QPointF(19, 8), QPointF(12, 12), QPointF(5, 8)])
        front_poly = QPolygonF([QPointF(5, 8), QPointF(12, 12), QPointF(12, 20), QPointF(5, 16)])
        right_poly = QPolygonF([QPointF(19, 8), QPointF(12, 12), QPointF(12, 20), QPointF(19, 16)])

        c_top = QColor(ACCENT_COLOR) if view_type == "top" else QColor("#cccccc")
        c_front = QColor(ACCENT_COLOR) if view_type == "front" else QColor("#999999")
        c_right = QColor(ACCENT_COLOR) if view_type == "right" else QColor("#777777")
        if view_type == "iso":
            c_top = QColor(ACCENT_COLOR).lighter(120)
            c_front = QColor(ACCENT_COLOR)
            c_right = QColor(ACCENT_COLOR).darker(140)

        p.setBrush(QBrush(c_top))
        p.drawPolygon(top_poly)
        p.setBrush(QBrush(c_front))
        p.drawPolygon(front_poly)
        p.setBrush(QBrush(c_right))
        p.drawPolygon(right_poly)
        p.end()
        return QIcon(pix)


# ---------------------------------------------------------------------------
# ViewportFrame: HUD Header & Border Overlay
# ---------------------------------------------------------------------------

class ViewportFocusFilter(QObject):
    """Filters events on Viewport to track active focus."""

    def __init__(self, frame: "ViewportFrame") -> None:
        super().__init__(frame)
        self.frame = frame

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.MouseButtonPress, QEvent.FocusIn):
            self.frame.container.set_active_frame(self.frame)
        return super().eventFilter(watched, event)


class ViewportFrame(QFrame):
    """Wraps an OpenGL Viewport with a CAD-style HUD header and active border."""

    def __init__(
        self,
        container: "MultiViewportContainer",
        viewport: Viewport,
        title: str,
        default_view: str = "persp",
        is_primary: bool = False,
    ) -> None:
        super().__init__(container)
        self.container = container
        self.viewport = viewport
        self.view_name = title
        self.default_view = default_view
        self.is_primary = is_primary
        self.is_active = False

        self._build_ui()
        self._setup_event_filter()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # Header Bar
        self.header = QFrame(self)
        self.header.setFixedHeight(24)
        self.header.setStyleSheet(
            f"background-color: {BG_HEADER}; border-bottom: 1px solid {BORDER_INACTIVE};"
        )
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(6, 0, 6, 0)
        h_layout.setSpacing(4)

        # View Selector Button
        self.btn_view = QToolButton(self.header)
        self.btn_view.setText(f"{self.view_name} ▾")
        self.btn_view.setStyleSheet(
            f"QToolButton {{ color: {TEXT_COLOR}; font-weight: bold; font-size: 10px; background: transparent; border: none; }} "
            f"QToolButton:hover {{ color: {ACCENT_COLOR}; }}"
        )
        self.btn_view.setPopupMode(QToolButton.InstantPopup)
        self._build_view_menu()
        h_layout.addWidget(self.btn_view)

        # Style Selector Button
        self.btn_style = QToolButton(self.header)
        self.btn_style.setText("Style ▾")
        self.btn_style.setStyleSheet(
            f"QToolButton {{ color: #aaaaaa; font-size: 10px; background: transparent; border: none; }} "
            f"QToolButton:hover {{ color: {ACCENT_COLOR}; }}"
        )
        self.btn_style.setPopupMode(QToolButton.InstantPopup)
        self._build_style_menu()
        h_layout.addWidget(self.btn_style)

        h_layout.addStretch(1)

        # Maximize / Restore Button
        self.btn_max = QToolButton(self.header)
        self.btn_max.setText("⛶")
        self.btn_max.setToolTip(tr("Toggle Maximize / Quad View (Alt+W)"))
        self.btn_max.setStyleSheet(
            f"QToolButton {{ color: {TEXT_COLOR}; font-size: 12px; background: transparent; border: none; }} "
            f"QToolButton:hover {{ color: {ACCENT_COLOR}; }}"
        )
        self.btn_max.clicked.connect(self._toggle_maximize)
        h_layout.addWidget(self.btn_max)

        layout.addWidget(self.header)
        layout.addWidget(self.viewport, stretch=1)
        self.viewport.show()

        self.update_style()

    def _setup_event_filter(self) -> None:
        self.focus_filter = ViewportFocusFilter(self)
        self.viewport.installEventFilter(self.focus_filter)

    def set_viewport(self, new_vp: Viewport) -> None:
        """Swap the underlying Viewport widget (used when switching Document tabs)."""
        if self.viewport is new_vp:
            if new_vp is not None:
                if new_vp.parent() is not self:
                    self.layout().addWidget(new_vp, 1)
                new_vp.show()
            return

        old_vp = self.viewport
        layout = self.layout()
        if old_vp is not None:
            try:
                old_vp.removeEventFilter(self.focus_filter)
            except Exception:
                pass
            try:
                old_vp.sceneVersionChanged.disconnect(self.container.update_all_viewports)
            except Exception:
                pass
            if layout is not None:
                layout.removeWidget(old_vp)
            old_vp.hide()
            doc_stack = getattr(self.container.window, "_doc_stack", None)
            if doc_stack is not None and doc_stack.indexOf(old_vp) < 0:
                doc_stack.addWidget(old_vp)
                old_vp.hide()

        self.viewport = new_vp
        if new_vp is not None:
            label = new_vp.property("multiviewTitle")
            if not label:
                label = "Perspective" if new_vp.camera.perspective else "Parallel"
            self.set_view_title(label)
            if layout is not None:
                layout.addWidget(new_vp, 1)
            new_vp.installEventFilter(self.focus_filter)
            try:
                new_vp.sceneVersionChanged.connect(self.container.update_all_viewports)
            except Exception:
                pass
            new_vp.show()

    def _build_view_menu(self) -> None:
        menu = QMenu(self.btn_view)
        views = [
            ("Top (Parallel)", "top", False),
            ("Front (Parallel)", "front", False),
            ("Right (Parallel)", "right", False),
            ("Left (Parallel)", "left", False),
            ("Back (Parallel)", "back", False),
            ("Bottom (Parallel)", "bottom", False),
            ("Isometric (Parallel)", "iso", False),
            ("Perspective (3D)", "iso", True),
        ]
        for label, cam_name, persp in views:
            act = menu.addAction(label)
            act.triggered.connect(
                lambda checked=False, cn=cam_name, p=persp, l=label: self.set_view(cn, p, l)
            )
        menu.addSeparator()
        act_proj = menu.addAction(tr("Toggle Perspective / Parallel"))
        act_proj.triggered.connect(self._toggle_projection)
        self.btn_view.setMenu(menu)

    def _build_style_menu(self) -> None:
        menu = QMenu(self.btn_style)
        styles = [
            ("Wireframe", "Wireframe"),
            ("Hidden line", "Hidden line"),
            ("Shaded", "Shaded"),
            ("Textures (Default)", "Default"),
            ("Monochrome", "Monochrome"),
            ("X-ray", "X-ray"),
        ]
        for label, s_name in styles:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, sn=s_name: self.set_style(sn))
        self.btn_style.setMenu(menu)

    def set_view(self, cam_name: str, perspective: bool, label: str) -> None:
        self.container.set_active_frame(self)
        self.viewport.camera.set_view(cam_name)
        self.viewport.camera.perspective = perspective
        self.set_view_title(label.split(" (")[0])
        self.viewport.update()

    def set_view_title(self, label: str) -> None:
        self.view_name = label
        self.viewport.setProperty("multiviewTitle", label)
        self.btn_view.setText(f"{self.view_name} ▾")

    def set_style(self, style_name: str) -> None:
        self.container.set_active_frame(self)
        st = core.style.style_by_name(style_name)
        if st:
            self.container.window._apply_display_style(st)
        self.container.update_all_viewports()

    def _toggle_projection(self) -> None:
        self.container.set_active_frame(self)
        self.viewport.camera.toggle_projection()
        self.viewport.update()

    def _toggle_maximize(self) -> None:
        self.container.toggle_maximize(self)

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_maximize()

    def set_active(self, active: bool) -> None:
        self.is_active = active
        self.update_style()

    def update_style(self) -> None:
        border_col = ACCENT_COLOR if self.is_active else BORDER_INACTIVE
        header_bg = BG_HEADER_ACTIVE if self.is_active else BG_HEADER
        self.setStyleSheet(
            f"ViewportFrame {{ border: 1.5px solid {border_col}; background: transparent; }}"
        )
        self.header.setStyleSheet(
            f"background-color: {header_bg}; border-bottom: 1px solid {border_col};"
        )


# ---------------------------------------------------------------------------
# MultiViewportContainer: Synchronized 4-Way Crosshair Splitter
# ---------------------------------------------------------------------------

class MultiViewportContainer(QWidget):
    """Container managing 1 to 4 viewports with linked splitters and synchronization."""

    MODE_SINGLE = "single"
    MODE_QUAD = "quad"
    MODE_SPLIT_H = "split_h"
    MODE_SPLIT_V = "split_v"

    def __init__(self, window, primary_viewport: Viewport) -> None:
        super().__init__(window)
        self.window = window
        self.primary_viewport = primary_viewport
        self.current_mode = self.MODE_SINGLE
        self._restore_mode = self.MODE_QUAD
        self._splitter_sizes = {}
        self.is_attached = False

        doc = getattr(self.window, "_doc", None)
        if doc is not None and not hasattr(doc, "_true_viewport"):
            doc._true_viewport = primary_viewport

        self._build_viewports()
        self._build_layout()
        self._setup_sync()
        self.attach_to_window()
        self.set_layout_mode(self.MODE_SINGLE)

    def _make_secondary_viewport(self, view_name: str) -> Viewport:
        vp = Viewport(self)
        for attr in ("_ext_overlays", "_ext_snap_providers", "_ext_pickables"):
            if hasattr(self.primary_viewport, attr):
                setattr(vp, attr, getattr(self.primary_viewport, attr))
        vp.scene = self.primary_viewport.scene
        vp.history = self.primary_viewport.history
        vp.camera.set_view(view_name)
        vp.camera.perspective = False
        if hasattr(self.window, "_wire_viewport"):
            try:
                self.window._wire_viewport(vp)
            except Exception:
                pass
        return vp

    def _build_viewports(self) -> None:
        # Perspective 3D (Primary Viewport)
        self.frame_persp = ViewportFrame(
            self, self.primary_viewport, "Perspective", "persp", is_primary=True
        )

        # Top View (Orthographic)
        vp_top = self._make_secondary_viewport("top")
        self.frame_top = ViewportFrame(self, vp_top, "Top", "top")

        # Front View (Orthographic)
        vp_front = self._make_secondary_viewport("front")
        self.frame_front = ViewportFrame(self, vp_front, "Front", "front")

        # Right View (Orthographic)
        vp_right = self._make_secondary_viewport("right")
        self.frame_right = ViewportFrame(self, vp_right, "Right", "right")

        self.frames = [
            self.frame_top,
            self.frame_persp,
            self.frame_front,
            self.frame_right,
        ]
        self.active_frame = self.frame_persp
        self.frame_persp.set_active(True)

    def _build_layout(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Synchronized 2x2 Splitter Setup
        self.v_split = QSplitter(Qt.Vertical, self)
        self.h_top = QSplitter(Qt.Horizontal, self.v_split)
        self.h_bot = QSplitter(Qt.Horizontal, self.v_split)

        # Top Row: Top | Perspective
        self.h_top.addWidget(self.frame_top)
        self.h_top.addWidget(self.frame_persp)

        # Bottom Row: Front | Right
        self.h_bot.addWidget(self.frame_front)
        self.h_bot.addWidget(self.frame_right)

        self.v_split.addWidget(self.h_top)
        self.v_split.addWidget(self.h_bot)

        main_layout.addWidget(self.v_split)

        for splitter in (self.v_split, self.h_top, self.h_bot):
            splitter.setChildrenCollapsible(False)
            splitter.setHandleWidth(10)
            splitter.setStyleSheet(
                "QSplitter::handle { background: #333333; }"
                f"QSplitter::handle:hover {{ background: {ACCENT_COLOR}; }}"
            )

        # Crosshair Splitter Linking
        self.h_top.splitterMoved.connect(
            lambda *_: self._resize_panes(self.h_top, self.h_bot)
        )
        self.h_bot.splitterMoved.connect(
            lambda *_: self._resize_panes(self.h_bot, self.h_top)
        )
        self.v_split.splitterMoved.connect(lambda *_: self._resize_panes(self.v_split))

    def _resize_panes(self, splitter: QSplitter, peer: Optional[QSplitter] = None) -> None:
        sizes = splitter.sizes()
        if self.current_mode == self.MODE_QUAD and peer is not None:
            peer.setSizes(sizes)
        self._splitter_sizes[self.current_mode] = (
            self.v_split.sizes(), self.h_top.sizes(), self.h_bot.sizes()
        )

    def _setup_sync(self) -> None:
        # Cross-viewport redraw on geometry mutation
        for f in self.frames:
            f.viewport.sceneVersionChanged.connect(self.update_all_viewports)

    def _secondary_viewports(self) -> set[Viewport]:
        return {
            self.frame_top.viewport,
            self.frame_front.viewport,
            self.frame_right.viewport,
        }

    def _ensure_true_viewport(self, doc) -> Optional[Viewport]:
        if doc is None:
            return None
        true_vp = getattr(doc, "_true_viewport", None)
        if true_vp is None and getattr(doc, "viewport", None) is not None:
            if doc.viewport not in self._secondary_viewports():
                doc._true_viewport = doc.viewport
                true_vp = doc.viewport
        return true_vp

    def sync_secondary_viewports(self) -> None:
        """Synchronize secondary orthographic viewports with primary_viewport's scene and history."""
        if self.primary_viewport is None:
            return
        scene = self.primary_viewport.scene
        history = self.primary_viewport.history
        active_tool = getattr(self.primary_viewport, "active_tool", None)

        for f in self.frames:
            if not f.is_primary:
                vp = f.viewport
                vp.end_group_edit()
                vp.inference.reset()
                vp.reset_document_caches()
                vp.scene = scene
                vp.history = history
                vp._edges_version = -1
                vp._hover_entity = None
                vp._hover_edge = None
                vp.last_snap = None
                vp.reference_edge = None
                vp.reference_mode = None
                if active_tool is not None and vp.active_tool is not active_tool:
                    vp.set_active_tool(active_tool)
                vp.show()
                vp.update()

    def attach_to_document(self, doc=None) -> None:
        """Bind MultiViewportContainer to the given (or currently active) Document."""
        if doc is None:
            doc = getattr(self.window, "_doc", None)

        if doc is None:
            # Fallback for single-document architecture
            if not self.is_attached:
                self.window.setCentralWidget(self)
                self.is_attached = True
            self.frame_persp.viewport.show()
            self.sync_secondary_viewports()
            return

        true_vp = self._ensure_true_viewport(doc)
        if true_vp is None:
            return

        # Clear stand_in from any other document so only the active document owns this container
        for d in getattr(self.window, "_documents", []):
            if d is not doc and getattr(d, "stand_in", None) is self:
                d.stand_in = None
                d_true = self._ensure_true_viewport(d)
                if d_true is not None:
                    d.viewport = d_true

        # Restore doc.viewport to true_vp before setCentralWidget so MainWindow doesn't retire true_vp
        doc.viewport = true_vp
        self.primary_viewport = true_vp

        if getattr(doc, "stand_in", None) is not self:
            self.window.setCentralWidget(self)

        doc_stack = getattr(self.window, "_doc_stack", None)
        if doc_stack is not None:
            if doc_stack.indexOf(self) < 0:
                doc_stack.addWidget(self)
            if getattr(self.window, "_doc", None) is doc:
                doc_stack.setCurrentWidget(self)

        # Ensure frame_persp holds this document's primary viewport and is explicitly visible
        self.frame_persp.set_viewport(true_vp)
        true_vp.show()
        self.show()

        # Sync secondary viewports to this document's scene & history
        self.sync_secondary_viewports()

        # Keep window.viewport pointing to the active frame's viewport
        if self.active_frame is not None:
            self.window.viewport = self.active_frame.viewport

        self.is_attached = True
        self.update_all_viewports()

    def attach_to_window(self) -> None:
        """Attach multi-viewport container into MainWindow central widget safely."""
        self.attach_to_document(getattr(self.window, "_doc", None))

    def update_all_viewports(self) -> None:
        for f in self.frames:
            f.viewport.update()

    def set_tool_on_all(self, tool) -> None:
        for f in self.frames:
            if f is not self.active_frame:
                f.viewport.set_active_tool(tool)
        if self.active_frame is not None:
            self.active_frame.viewport.set_active_tool(tool)

    def set_active_frame(self, frame: ViewportFrame) -> None:
        doc = getattr(self.window, "_doc", None)
        if doc is not None:
            self._ensure_true_viewport(doc)

        if self.active_frame == frame:
            self.window.viewport = frame.viewport
            return

        prev_tool = None
        if self.active_frame is not None and self.active_frame.viewport is not None:
            prev_tool = self.active_frame.viewport.active_tool
        if prev_tool is None and self.primary_viewport is not None:
            prev_tool = self.primary_viewport.active_tool

        for f in self.frames:
            f.set_active(f == frame)
        self.active_frame = frame
        self.window.viewport = frame.viewport

        # Align current active tool
        if hasattr(self.window, "_tool_key") and prev_tool is not None:
            key = self.window._tool_key(prev_tool)
            tool = self.window._tools.get(key) if key else prev_tool
            if tool:
                frame.viewport.set_active_tool(tool)

        self.window.statusBar().showMessage(
            tr("Active Viewport: {name}", name=frame.view_name), 1500
        )

    def _apply_visibility_for_mode(self, mode: str) -> None:
        target = self.active_frame or self.frame_persp
        if mode == self.MODE_QUAD:
            visible = self.frames
        elif mode == self.MODE_SPLIT_H:
            visible = (self.frame_top, self.frame_front)
        elif mode == self.MODE_SPLIT_V:
            visible = (self.frame_persp, self.frame_top)
        else:
            visible = (target,)

        self.h_top.setVisible(self.frame_top in visible or self.frame_persp in visible)
        self.h_bot.setVisible(self.frame_front in visible or self.frame_right in visible)
        for frame in self.frames:
            frame.setVisible(frame in visible)
        if target not in visible:
            self.set_active_frame(visible[0])

        # Hidden children fill the remaining space automatically. Set sizes
        # only for dividers that actually exist in the selected layout.
        half_height = max(self.height(), 600) // 2
        half_width = max(self.width(), 800) // 2
        rows, top, bottom = self._splitter_sizes.get(
            mode, ([half_height] * 2, [half_width] * 2, [half_width] * 2)
        )
        if mode in (self.MODE_QUAD, self.MODE_SPLIT_H):
            self.v_split.setSizes(rows)
        if mode in (self.MODE_QUAD, self.MODE_SPLIT_V):
            self.h_top.setSizes(top)
        if mode == self.MODE_QUAD:
            self.h_bot.setSizes(bottom)

    def set_layout_mode(self, mode: str) -> None:
        if mode != self.MODE_SINGLE:
            self._restore_mode = mode
        self.current_mode = mode
        self._apply_visibility_for_mode(mode)
        self.update_all_viewports()

    def toggle_maximize(self, frame: Optional[ViewportFrame] = None) -> None:
        if frame:
            self.set_active_frame(frame)
        if self.current_mode == self.MODE_SINGLE:
            self.set_layout_mode(self._restore_mode)
        else:
            self.set_layout_mode(self.MODE_SINGLE)


# ---------------------------------------------------------------------------
# Controllers
# ---------------------------------------------------------------------------

class VisibilityController:
    """Manages Hide, Unhide, and Isolate actions."""

    def __init__(self, window, container: Optional[MultiViewportContainer] = None) -> None:
        self.window = window
        self.container = container

    def hide_selected(self) -> None:
        self.window._on_hide()
        if self.container:
            self.container.update_all_viewports()

    def unhide_all(self) -> None:
        self.window._on_unhide_all()
        if self.container:
            self.container.update_all_viewports()

    def unhide_last(self) -> None:
        self.window._on_unhide_last()
        if self.container:
            self.container.update_all_viewports()

    def isolate_selection(self) -> None:
        self.window._on_invert_selection()
        self.window._on_hide()
        if self.container:
            self.container.update_all_viewports()
        self.window.statusBar().showMessage(tr("Selection Isolated"), 2000)


class StyleController:
    """Manages Display Style switching and toggles."""

    def __init__(self, window, container: Optional[MultiViewportContainer] = None) -> None:
        self.window = window
        self.container = container

    def apply_style(self, style_name: str) -> None:
        st = core.style.style_by_name(style_name)
        if st:
            self.window._apply_display_style(st)
            if self.container:
                self.container.update_all_viewports()

    def toggle_edges(self) -> None:
        vp = self.window.viewport
        style = vp.scene.display_style
        style.edges = not style.edges
        if self.container:
            self.container.update_all_viewports()
        else:
            vp.update()
        state_str = tr("On") if style.edges else tr("Off")
        self.window.statusBar().showMessage(
            tr("Edges: {state}", state=state_str), 1500
        )


class ViewController:
    """Manages Camera Views, Projections, and Viewport Layouts."""

    def __init__(self, window, container: MultiViewportContainer) -> None:
        self.window = window
        self.container = container

    def set_view(self, name: str) -> None:
        self.window._on_standard_view(name)
        if self.container.active_frame is not None:
            label_map = {
                "top": "Top",
                "front": "Front",
                "right": "Right",
                "left": "Left",
                "back": "Back",
                "bottom": "Bottom",
                "iso": "Isometric",
            }
            if name in label_map:
                self.container.active_frame.set_view_title(label_map[name])

    def toggle_projection(self) -> None:
        self.window.viewport.camera.toggle_projection()
        self.window.viewport.update()

    def zoom_extents(self) -> None:
        self.window._on_zoom_extents()

    def set_mode(self, mode: str) -> None:
        self.container.set_layout_mode(mode)

    def toggle_maximize(self) -> None:
        self.container.toggle_maximize()


# ---------------------------------------------------------------------------
# Plugin Master
# ---------------------------------------------------------------------------

class ViewToolsPlugin:
    """Main plugin manager coordinating toolbars, shortcuts, and containers."""

    def __init__(self, app) -> None:
        self.app = app
        self.window = app.window if not callable(app.window) else app.window()
        self.primary_viewport = app.viewport if not callable(app.viewport) else app.viewport()

        # Container & Controllers
        self.container = MultiViewportContainer(self.window, self.primary_viewport)
        self.visibility = VisibilityController(self.window, self.container)
        self.styles = StyleController(self.window, self.container)
        self.views = ViewController(self.window, self.container)

        # Hook tool activations and document tab lifecycle across all viewports
        self._hook_tools()
        self._hook_documents()

        # Build UI
        self._build_toolbars()
        self._register_shortcuts()

    def on_document_changed(self) -> None:
        """Keep primary and secondary viewports linked when a document is opened or reset."""
        doc = getattr(self.window, "_doc", None)
        if doc is not None:
            true_vp = self.container._ensure_true_viewport(doc)
            if true_vp is not None:
                self.primary_viewport = true_vp
        self.container.attach_to_document(doc)

    def _hook_tools(self) -> None:
        orig_activate_tool = self.window._activate_tool

        def hooked_activate_tool(key):
            orig_activate_tool(key)
            tool = self.window._tools.get(key)
            if tool:
                self.container.set_tool_on_all(tool)

        self.window._activate_tool = hooked_activate_tool

        if hasattr(self.window, "_activate_plugin_tool"):
            orig_activate_plugin_tool = self.window._activate_plugin_tool

            def hooked_activate_plugin_tool(key):
                orig_activate_plugin_tool(key)
                tool = self.window._tools.get(key)
                if tool:
                    self.container.set_tool_on_all(tool)

            self.window._activate_plugin_tool = hooked_activate_plugin_tool

    def _hook_documents(self) -> None:
        """Hook IngeTrazo 0.6 multi-document tab lifecycle methods."""
        if hasattr(self.window, "_leave_document"):
            orig_leave = self.window._leave_document

            def hooked_leave_document(doc, *, picture=True):
                if doc is not None:
                    for f in self.container.frames:
                        try:
                            f.viewport.end_group_edit()
                        except Exception:
                            pass
                    true_vp = self.container._ensure_true_viewport(doc)
                    if true_vp is not None:
                        doc.viewport = true_vp
                orig_leave(doc, picture=picture)
                if doc is not None and getattr(doc, "stand_in", None) is self.container:
                    doc.stand_in = None

            self.window._leave_document = hooked_leave_document

        if hasattr(self.window, "_enter_document"):
            orig_enter = self.window._enter_document

            def hooked_enter_document(doc):
                if doc is not None:
                    true_vp = self.container._ensure_true_viewport(doc)
                    if true_vp is not None:
                        doc.viewport = true_vp
                        self.primary_viewport = true_vp
                orig_enter(doc)
                if doc is not None:
                    self.container.attach_to_document(doc)

            self.window._enter_document = hooked_enter_document

        if hasattr(self.window, "_retire_document"):
            orig_retire = self.window._retire_document

            def hooked_retire_document(doc):
                if doc is not None:
                    true_vp = getattr(doc, "_true_viewport", None)
                    if true_vp is not None:
                        doc.viewport = true_vp
                    if getattr(doc, "stand_in", None) is self.container:
                        doc.stand_in = None
                    if self.container.frame_persp.viewport is doc.viewport:
                        active_doc = getattr(self.window, "_doc", None)
                        next_vp = (
                            self.container._ensure_true_viewport(active_doc)
                            if active_doc is not None and active_doc is not doc
                            else None
                        )
                        self.container.frame_persp.set_viewport(next_vp)
                orig_retire(doc)

            self.window._retire_document = hooked_retire_document

        if hasattr(self.window, "enter_workspace"):
            orig_enter_ws = self.window.enter_workspace

            def hooked_enter_workspace(workspace):
                doc = getattr(self.window, "_doc", None)
                true_vp = self.container._ensure_true_viewport(doc)
                if true_vp is not None:
                    self.window.viewport = true_vp
                res = orig_enter_ws(workspace)
                if res:
                    self.container.sync_secondary_viewports()
                if self.container.active_frame is not None:
                    self.window.viewport = self.container.active_frame.viewport
                return res

            self.window.enter_workspace = hooked_enter_workspace

        if hasattr(self.window, "leave_workspace"):
            orig_leave_ws = self.window.leave_workspace

            def hooked_leave_workspace():
                doc = getattr(self.window, "_doc", None)
                true_vp = self.container._ensure_true_viewport(doc)
                if true_vp is not None:
                    self.window.viewport = true_vp
                res = orig_leave_ws()
                if res:
                    self.container.sync_secondary_viewports()
                if self.container.active_frame is not None:
                    self.window.viewport = self.container.active_frame.viewport
                return res

            self.window.leave_workspace = hooked_leave_workspace

        if hasattr(self.window, "all_viewports"):
            orig_all_vps = self.window.all_viewports

            def hooked_all_viewports():
                vps = []
                for d in getattr(self.window, "_documents", []):
                    vp = getattr(d, "_true_viewport", None) or getattr(d, "viewport", None)
                    if vp is not None and vp not in vps:
                        vps.append(vp)
                for f in self.container.frames:
                    if f.viewport is not None and f.viewport not in vps:
                        vps.append(f.viewport)
                return vps if vps else orig_all_vps()

            self.window.all_viewports = hooked_all_viewports

    def _build_toolbars(self) -> None:
        # 1. Visibility Toolbar
        tb_vis = self.window._new_toolbar("Visibility", "toolbar_visibility")

        act_hide = tb_vis.addAction(IconVault.hide_selected(), tr("Hide Selected (Ctrl+H)"))
        act_hide.setShortcut(QKeySequence("Ctrl+H"))
        act_hide.triggered.connect(self.visibility.hide_selected)

        act_unhide_all = tb_vis.addAction(IconVault.unhide_all(), tr("Unhide All (Ctrl+Shift+H)"))
        act_unhide_all.setShortcut(QKeySequence("Ctrl+Shift+H"))
        act_unhide_all.triggered.connect(self.visibility.unhide_all)

        act_unhide_last = tb_vis.addAction(IconVault.unhide_last(), tr("Unhide Last (Ctrl+Alt+H)"))
        act_unhide_last.setShortcut(QKeySequence("Ctrl+Alt+H"))
        act_unhide_last.triggered.connect(self.visibility.unhide_last)

        act_isolate = tb_vis.addAction(IconVault.isolate_selection(), tr("Isolate Selection (Ctrl+I)"))
        act_isolate.setShortcut(QKeySequence("Ctrl+I"))
        act_isolate.triggered.connect(self.visibility.isolate_selection)

        tb_vis.show()

        # 2. Display Styles Toolbar
        tb_styles = self.window._new_toolbar("Display Styles", "toolbar_display_styles")

        style_defs = [
            ("Wireframe", "Wireframe (F2)", "F2", IconVault.wireframe()),
            ("Hidden line", "Hidden Line (F3)", "F3", IconVault.hidden_line()),
            ("Shaded", "Shaded (F4)", "F4", IconVault.shaded()),
            ("Default", "Textures (F5)", "F5", IconVault.textures()),
            ("Monochrome", "Monochrome (F6)", "F6", IconVault.monochrome()),
            ("X-ray", "X-Ray (F7)", "F7", IconVault.xray()),
        ]
        for s_name, label, sc, icon in style_defs:
            act = tb_styles.addAction(icon, tr(label))
            act.setShortcut(QKeySequence(sc))
            act.triggered.connect(lambda checked=False, sn=s_name: self.styles.apply_style(sn))

        tb_styles.addSeparator()
        act_edges = tb_styles.addAction(IconVault.toggle_edges(), tr("Toggle Edges"))
        act_edges.triggered.connect(self.styles.toggle_edges)

        tb_styles.show()

        # 3. Viewports & Views Toolbar
        tb_views = self.window._new_toolbar("Viewports & Views", "toolbar_viewports_views")

        act_single = tb_views.addAction(IconVault.view_single(), tr("Single Viewport"))
        act_single.triggered.connect(lambda: self.views.set_mode(MultiViewportContainer.MODE_SINGLE))

        act_quad = tb_views.addAction(IconVault.view_quad(), tr("Quad View (Alt+W / Ctrl+Alt+Q)"))
        act_quad.setShortcut(QKeySequence("Alt+W"))
        act_quad.triggered.connect(self.views.toggle_maximize)

        act_split_h = tb_views.addAction(IconVault.view_split_h(), tr("Split Horizontal (2 Views)"))
        act_split_h.triggered.connect(lambda: self.views.set_mode(MultiViewportContainer.MODE_SPLIT_H))

        act_split_v = tb_views.addAction(IconVault.view_split_v(), tr("Split Vertical (2 Views)"))
        act_split_v.triggered.connect(lambda: self.views.set_mode(MultiViewportContainer.MODE_SPLIT_V))

        tb_views.addSeparator()

        cam_defs = [
            ("top", "Top View (Ctrl+1)", "Ctrl+1"),
            ("front", "Front View (Ctrl+2)", "Ctrl+2"),
            ("right", "Right View (Ctrl+3)", "Ctrl+3"),
            ("iso", "Isometric View (Ctrl+7)", "Ctrl+7"),
        ]
        for c_name, label, sc in cam_defs:
            act = tb_views.addAction(IconVault.standard_view(c_name), tr(label))
            act.setShortcut(QKeySequence(sc))
            act.triggered.connect(lambda checked=False, cn=c_name: self.views.set_view(cn))

        tb_views.show()

        if hasattr(self.app, "restore_toolbar_layout"):
            try:
                self.app.restore_toolbar_layout()
            except Exception:
                pass
        elif hasattr(self.window, "_wrap_toolbar_rows"):
            try:
                self.window._wrap_toolbar_rows()
            except Exception:
                pass

    def _register_shortcuts(self) -> None:
        # Extra convenience shortcuts
        alt_quad = QAction(self.window)
        alt_quad.setShortcut(QKeySequence("Ctrl+Alt+Q"))
        alt_quad.triggered.connect(self.views.toggle_maximize)
        self.window.addAction(alt_quad)

        # Standard views 4..6
        v4 = QAction(self.window)
        v4.setShortcut(QKeySequence("Ctrl+4"))
        v4.triggered.connect(lambda: self.views.set_view("left"))
        self.window.addAction(v4)

        v5 = QAction(self.window)
        v5.setShortcut(QKeySequence("Ctrl+5"))
        v5.triggered.connect(lambda: self.views.set_view("back"))
        self.window.addAction(v5)

        v6 = QAction(self.window)
        v6.setShortcut(QKeySequence("Ctrl+6"))
        v6.triggered.connect(lambda: self.views.set_view("bottom"))
        self.window.addAction(v6)


def setup(app) -> None:
    """Initialize the Multi-Viewport and View Tools Suite."""
    try:
        win = getattr(app, "window", None)
        if callable(win):
            win = win()
        if win is None:
            return

        if getattr(win, "_multi_viewport_plugin", None):
            return

        def _safe_init():
            try:
                if getattr(win, "_multi_viewport_plugin", None):
                    return
                plugin = ViewToolsPlugin(app)
                win._multi_viewport_plugin = plugin
                if hasattr(app, "on_document_changed"):
                    app.on_document_changed(plugin.on_document_changed)
            except Exception:
                traceback.print_exc()

        QTimer.singleShot(150, _safe_init)
    except Exception:
        traceback.print_exc()
