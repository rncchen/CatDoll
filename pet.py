import os
import sys
import random
from enum import Enum, auto

import numpy as np
from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QPixmap, QPainter, QImage, QAction, QIcon, QCursor
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon


COLS = 4
ROWS = 2

TARGET_HEIGHT = 96
SLEEP_SCALE = 0.75

WALK_TICK_MS = 50
WALK_FRAME_MS = 120
SLEEP_FRAME_MS = 250
WALK_SPEED_PX = 2

STATE_MIN_MS = 5000
STATE_MAX_MS = 10000


def asset_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def cache_dir() -> str:
    if hasattr(sys, "_MEIPASS"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "CatDoll")
    else:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
    os.makedirs(d, exist_ok=True)
    return d


def load_processed_sheet(name: str) -> QPixmap:
    src = asset_path(name)
    cached = os.path.join(cache_dir(), name.replace(".png", "_proc.png"))
    if os.path.exists(cached) and os.path.getmtime(cached) >= os.path.getmtime(src):
        return QPixmap(cached)
    pixmap = remove_white_bg(QPixmap(src))
    pixmap.save(cached, "PNG")
    return pixmap


def remove_white_bg(pixmap: QPixmap, threshold: int = 240) -> QPixmap:
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()

    ptr = img.bits()
    raw = np.frombuffer(memoryview(ptr).cast("B"), dtype=np.uint8)
    arr = raw.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)
    b, g, r = arr[..., 0], arr[..., 1], arr[..., 2]

    white = (r >= threshold) & (g >= threshold) & (b >= threshold)

    bg = np.zeros((h, w), dtype=bool)
    bg[0, :] = white[0, :]
    bg[-1, :] = white[-1, :]
    bg[:, 0] = white[:, 0]
    bg[:, -1] = white[:, -1]

    while True:
        new_bg = bg.copy()
        new_bg[1:, :] |= bg[:-1, :] & white[1:, :]
        new_bg[:-1, :] |= bg[1:, :] & white[:-1, :]
        new_bg[:, 1:] |= bg[:, :-1] & white[:, 1:]
        new_bg[:, :-1] |= bg[:, 1:] & white[:, :-1]
        if np.array_equal(new_bg, bg):
            break
        bg = new_bg

    adj_to_bg = np.zeros_like(bg)
    adj_to_bg[1:, :] |= bg[:-1, :]
    adj_to_bg[:-1, :] |= bg[1:, :]
    adj_to_bg[:, 1:] |= bg[:, :-1]
    adj_to_bg[:, :-1] |= bg[:, 1:]
    adj_to_bg &= ~bg

    min_ch = np.minimum(np.minimum(r, g), b).astype(np.int32)
    soft_lo, soft_hi = 180, 240
    soft_alpha = np.clip(
        (soft_lo + soft_hi - 2 * min_ch) * 255 // (soft_hi - soft_lo),
        0,
        255,
    ).astype(np.uint8)

    alpha = np.full((h, w), 255, dtype=np.uint8)
    alpha[bg] = 0
    edge_mask = adj_to_bg & (min_ch >= soft_lo)
    alpha[edge_mask] = np.minimum(alpha[edge_mask], soft_alpha[edge_mask])
    arr[..., 3] = alpha
    return QPixmap.fromImage(img.copy())


def _alpha_array(pixmap: QPixmap) -> np.ndarray:
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    bpl = img.bytesPerLine()
    ptr = img.bits()
    raw = np.frombuffer(memoryview(ptr).cast("B"), dtype=np.uint8)
    return raw.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4)[..., 3].copy()


def common_cell_bbox(alpha: np.ndarray, fw: int, fh: int) -> tuple[int, int, int, int]:
    x0_min, y0_min, x1_max, y1_max = fw, fh, 0, 0
    for r in range(ROWS):
        for c in range(COLS):
            cell = alpha[r * fh : (r + 1) * fh, c * fw : (c + 1) * fw]
            rows = np.where(cell.any(axis=1))[0]
            cols = np.where(cell.any(axis=0))[0]
            if rows.size == 0 or cols.size == 0:
                continue
            x0_min = min(x0_min, int(cols[0]))
            y0_min = min(y0_min, int(rows[0]))
            x1_max = max(x1_max, int(cols[-1]))
            y1_max = max(y1_max, int(rows[-1]))
    return x0_min, y0_min, x1_max - x0_min + 1, y1_max - y0_min + 1


def measure_sheet(pixmap: QPixmap) -> tuple[int, int, int, int, int, int]:
    fw = pixmap.width() // COLS
    fh = pixmap.height() // ROWS
    alpha = _alpha_array(pixmap)
    bx, by, bw, bh = common_cell_bbox(alpha, fw, fh)
    return fw, fh, bx, by, bw, bh


def slice_sheet(pixmap: QPixmap, scale: float) -> list[QPixmap]:
    fw = pixmap.width() // COLS
    fh = pixmap.height() // ROWS
    alpha = _alpha_array(pixmap)
    frames = []
    for r in range(ROWS):
        for c in range(COLS):
            cell = alpha[r * fh : (r + 1) * fh, c * fw : (c + 1) * fw]
            rows = np.where(cell.any(axis=1))[0]
            cols = np.where(cell.any(axis=0))[0]
            if rows.size == 0 or cols.size == 0:
                continue
            bx, by = int(cols[0]), int(rows[0])
            bw = int(cols[-1]) - bx + 1
            bh = int(rows[-1]) - by + 1
            cropped = pixmap.copy(QRect(c * fw + bx, r * fh + by, bw, bh))
            target_w = max(1, round(bw * scale))
            target_h = max(1, round(bh * scale))
            scaled = cropped.scaled(
                target_w,
                target_h,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            frames.append(scaled)
    return frames


class State(Enum):
    WALK_LEFT = auto()
    WALK_RIGHT = auto()
    SLEEP = auto()
    DRAGGING = auto()


class CatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        left_sheet = load_processed_sheet("catleft.png")
        right_sheet = load_processed_sheet("catright.png")
        sleep_sheet = load_processed_sheet("catsleep.png")

        walk_bbox_h = max(measure_sheet(left_sheet)[5], measure_sheet(right_sheet)[5])
        scale = TARGET_HEIGHT / walk_bbox_h

        left_raw = slice_sheet(left_sheet, scale)
        right_raw = slice_sheet(right_sheet, scale)
        sleep_raw = slice_sheet(sleep_sheet, scale * SLEEP_SCALE)

        canvas_w = max(f.width() for f in left_raw + right_raw + sleep_raw)
        canvas_h = max(f.height() for f in left_raw + right_raw + sleep_raw)

        self.left_frames = left_raw
        self.right_frames = right_raw
        self.sleep_frames = sleep_raw
        self.tray_icon_pixmap = sleep_raw[0]

        self.max_frame_w = max(f.width() for f in left_raw + right_raw + sleep_raw)

        self.state = State.WALK_LEFT
        self.frame_index = 0
        self.drag_offset = QPoint()

        avail = QApplication.primaryScreen().availableGeometry()
        self.cat_center_x = avail.right() - self.max_frame_w // 2
        self._apply_frame_geometry()

        self.walk_tick = QTimer(self)
        self.walk_tick.timeout.connect(self.on_walk_tick)
        self.walk_tick.start(WALK_TICK_MS)

        self.anim_tick = QTimer(self)
        self.anim_tick.timeout.connect(self.on_anim_tick)
        self.anim_tick.start(WALK_FRAME_MS)

        self.state_tick = QTimer(self)
        self.state_tick.setSingleShot(True)
        self.state_tick.timeout.connect(self.pick_random_state)
        self.schedule_next_state()

        self.tray = self._build_tray()
        if self.tray is not None:
            self.tray.show()

    def showEvent(self, event):
        super().showEvent(event)
        self._disable_win11_chrome()

    def _disable_win11_chrome(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            dwmapi = ctypes.windll.dwmapi
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_DONOTROUND = 1
            pref = ctypes.c_int(DWMWCP_DONOTROUND)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(pref),
                ctypes.sizeof(pref),
            )
            DWMWA_BORDER_COLOR = 34
            DWMWA_COLOR_NONE = 0xFFFFFFFE
            color = ctypes.c_uint(DWMWA_COLOR_NONE)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_BORDER_COLOR,
                ctypes.byref(color),
                ctypes.sizeof(color),
            )
        except Exception:
            pass

    def _build_tray(self) -> QSystemTrayIcon | None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icon = QIcon(self.tray_icon_pixmap)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("CatDoll")

        menu = QMenu()
        show_action = QAction("叫醒貓 (走走)", self)
        show_action.triggered.connect(
            lambda: self.set_state(random.choice([State.WALK_LEFT, State.WALK_RIGHT]))
        )
        sleep_action = QAction("讓貓睡覺", self)
        sleep_action.triggered.connect(lambda: self.set_state(State.SLEEP))
        quit_action = QAction("結束", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(show_action)
        menu.addAction(sleep_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)

        tray.activated.connect(self._on_tray_activated)
        return tray

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.tray.contextMenu().exec(QCursor.pos())

    def current_frames(self) -> list[QPixmap]:
        if self.state == State.WALK_LEFT:
            return self.left_frames
        if self.state == State.WALK_RIGHT:
            return self.right_frames
        return self.sleep_frames

    def paintEvent(self, _event):
        frames = self.current_frames()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, frames[self.frame_index % len(frames)])

    def _apply_frame_geometry(self):
        f = self.current_frames()[self.frame_index % len(self.current_frames())]
        avail = QApplication.primaryScreen().availableGeometry()
        new_w, new_h = f.width(), f.height()
        new_x = self.cat_center_x - new_w // 2
        new_y = avail.bottom() - new_h + 1
        if (new_w, new_h) != (self.width(), self.height()):
            self.setGeometry(new_x, new_y, new_w, new_h)
        else:
            self.move(new_x, new_y)
        self.update()

    def cat_x_bounds(self) -> tuple[int, int]:
        avail = QApplication.primaryScreen().availableGeometry()
        return avail.left() + self.max_frame_w // 2, avail.right() - self.max_frame_w // 2

    def on_walk_tick(self):
        if self.state == State.DRAGGING:
            return
        if self.state in (State.WALK_LEFT, State.WALK_RIGHT):
            x_min, x_max = self.cat_x_bounds()
            dx = -WALK_SPEED_PX if self.state == State.WALK_LEFT else WALK_SPEED_PX
            new_center = self.cat_center_x + dx
            if new_center < x_min:
                new_center = x_min
                self.set_state(State.WALK_RIGHT)
            elif new_center > x_max:
                new_center = x_max
                self.set_state(State.WALK_LEFT)
            self.cat_center_x = new_center
        self._apply_frame_geometry()

    def on_anim_tick(self):
        frames = self.current_frames()
        self.frame_index = (self.frame_index + 1) % len(frames)
        self._apply_frame_geometry()

    def schedule_next_state(self):
        self.state_tick.start(random.randint(STATE_MIN_MS, STATE_MAX_MS))

    def pick_random_state(self):
        if self.state == State.DRAGGING:
            self.schedule_next_state()
            return
        next_state = random.choices(
            [State.WALK_LEFT, State.WALK_RIGHT, State.SLEEP],
            weights=[4, 4, 3],
        )[0]
        self.set_state(next_state)
        self.schedule_next_state()

    def set_state(self, new_state: State):
        if new_state == self.state:
            return
        self.state = new_state
        self.frame_index = 0
        if new_state == State.SLEEP:
            self.anim_tick.start(SLEEP_FRAME_MS)
        elif new_state == State.DRAGGING:
            self.anim_tick.stop()
        else:
            self.anim_tick.start(WALK_FRAME_MS)
        self._apply_frame_geometry()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            self.set_state(State.DRAGGING)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self.state == State.DRAGGING and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.cat_center_x = new_pos.x() + self.width() // 2
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.state == State.DRAGGING:
            x_min, x_max = self.cat_x_bounds()
            self.cat_center_x = max(x_min, min(x_max, self.cat_center_x))
            direction = random.choice([State.WALK_LEFT, State.WALK_RIGHT])
            self.set_state(direction)
            self.schedule_next_state()

    def show_context_menu(self, global_pos: QPoint):
        menu = QMenu(self)
        sleep_action = QAction("睡覺", self)
        sleep_action.triggered.connect(lambda: self.set_state(State.SLEEP))
        walk_action = QAction("走走", self)
        walk_action.triggered.connect(
            lambda: self.set_state(random.choice([State.WALK_LEFT, State.WALK_RIGHT]))
        )
        quit_action = QAction("結束", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(sleep_action)
        menu.addAction(walk_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(global_pos)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cat = CatWindow()
    cat.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
