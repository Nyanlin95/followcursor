"""Countdown overlay — shows 3, 2, 1 before recording starts."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import QWidget

from .. import tokens as T


class CountdownOverlay(QWidget):
    """Full-window translucent overlay that counts 3 → 2 → 1 then emits finished."""

    finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.WindowType.Widget)
        self._count: int = 3
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        """Begin the 3-2-1 countdown sequence."""
        self._count = 3
        self.setVisible(True)
        self.raise_()
        self.update()
        self._timer.start()

    def _tick(self) -> None:
        self._count -= 1
        if self._count <= 0:
            self._timer.stop()
            self.setVisible(False)
            self.finished.emit()
        else:
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # dark overlay
        overlay = QColor(T.BG_LAYER_1)
        overlay.setAlpha(200)
        painter.fillRect(self.rect(), overlay)

        # countdown number
        font = QFont()
        font.setFamily("Segoe UI Variable")
        font.setPixelSize(120)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 230))

        text = str(self._count)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.ascent()
        x = (self.width() - tw) // 2
        y = (self.height() + th) // 2 - 20

        # glow ring
        cx, cy = self.width() // 2, self.height() // 2
        for r in range(80, 40, -5):
            alpha = int(30 * (80 - r) / 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(T.BRAND_R, T.BRAND_G, T.BRAND_B, alpha))
            painter.drawEllipse(cx - r, cy - r - 20, r * 2, r * 2)

        # text
        painter.setPen(QColor(255, 255, 255, 230))
        painter.drawText(x, y, text)

        # subtitle
        sub_font = QFont()
        sub_font.setFamily("Segoe UI Variable")
        sub_font.setPixelSize(18)
        painter.setFont(sub_font)
        painter.setPen(QColor(T.FG_2))
        sub = "Recording starts…"
        sw = painter.fontMetrics().horizontalAdvance(sub)
        painter.drawText((self.width() - sw) // 2, y + 50, sub)

        painter.end()
