"""Tests for cursor interpolation helpers."""

import pytest
from PySide6.QtWidgets import QApplication

from app.cursor_renderer import _build_cursor_template, _interp_mouse_smooth
from app.models import MousePosition


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_interp_mouse_smooth_reduces_single_sample_jitter() -> None:
    track = [
        MousePosition(x=100, y=100, timestamp=0),
        MousePosition(x=104, y=96, timestamp=16),
        MousePosition(x=100, y=100, timestamp=32),
    ]

    x, y = _interp_mouse_smooth(track, 16, window_ms=40)

    assert 100.0 < x < 104.0
    assert 96.0 < y < 100.0
    assert abs(x - 100.0) < abs(104.0 - 100.0)
    assert abs(y - 100.0) < abs(96.0 - 100.0)


def test_interp_mouse_smooth_falls_back_for_tiny_tracks() -> None:
    track = [
        MousePosition(x=0, y=0, timestamp=0),
        MousePosition(x=100, y=100, timestamp=100),
    ]

    x, y = _interp_mouse_smooth(track, 50, window_ms=40)

    assert x == pytest.approx(50.0)
    assert y == pytest.approx(50.0)


def test_cursor_template_is_slim_and_tip_aligned(qapp) -> None:
    cursor_bgr, cursor_alpha = _build_cursor_template(48)

    assert cursor_bgr.shape[:2] == cursor_alpha.shape
    assert cursor_alpha.shape[0] > cursor_alpha.shape[1]
    assert cursor_alpha[0, 0] > 0
