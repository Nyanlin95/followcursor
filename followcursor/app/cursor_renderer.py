"""Mouse cursor renderer — draws a cursor overlay on video frames.

Provides both QPainter-based (for live preview) and numpy/OpenCV-based
(for export) cursor drawing using the recorded mouse track data.
Also renders click ripple effects at recorded click positions.
"""

import logging
import bisect
import math
from typing import List, Optional, Tuple

import cv2
import numpy as np

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPen,
    QBrush,
)
from PySide6.QtSvg import QSvgRenderer

from .models import MousePosition, ClickEvent, ClickEffectPreset, DEFAULT_CLICK_EFFECT, ZoomKeyframe
from .zoom_engine import compute_cursor_transition, ease_in_out

logger = logging.getLogger(__name__)


# ── Cursor appearance — blue voxel pointer ──────────────────────────

CURSOR_COLOR = (191, 219, 254)         # light blue fill (#bfdbfe)
CURSOR_OUTLINE = (37, 99, 235)        # vibrant blue border (#2563eb)
CURSOR_TOP = (147, 197, 253)          # top face highlight (#93c5fd)
CURSOR_SIDE = (29, 78, 216)            # right depth face (#1d4ed8)
CURSOR_INNER_SIDE = (59, 130, 246)     # inner cube depth (#3b82f6)
CURSOR_DEPTH = (30, 58, 138)           # extruded shadow cubes (#1e3a8a)
CURSOR_SHADOW = (23, 37, 84)           # drop shadow (#172554)
CURSOR_SHADOW_ALPHA = 72               # drop shadow opacity (0-255)

VOXEL_SIZE = 5                         # pixels per cube face
_VOXEL_DEPTH = 1                       # depth offset in voxel units

# Stepped arrow mask — tip at top-left (0, 0). Each row is one scanline.
_VOXEL_ROWS = (
    "X",
    "XX",
    "XXX",
    "XXXX",
    "XXXXX",
    "XXXXXX",
    "XXXXXXX",
    "XXXXXXX",
    "XXX  XX",
    "XX   XX",
    "X    XX",
    "     XX",
    "     XXX",
    "      XX",
)

# Arrow-tip (hotspot) in SVG coordinates
_TIP_SVG_X, _TIP_SVG_Y = 0.0, 0.0
_TIP_NX = 0.0
_TIP_NY = 0.0


def _voxel_cells_from_rows(rows: Tuple[str, ...]) -> Tuple[set[tuple[int, int]], int, int]:
    """Parse a row mask into occupied grid cells and grid dimensions."""
    width = max(len(row) for row in rows)
    cells: set[tuple[int, int]] = set()
    for y, row in enumerate(rows):
        padded = row.ljust(width)
        for x, ch in enumerate(padded):
            if ch not in (" ", "."):
                cells.add((x, y))
    return cells, width, len(rows)


def _voxel_is_border(x: int, y: int, cells: set[tuple[int, int]]) -> bool:
    """Return True when a filled cell touches empty space (outline voxel)."""
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        if (x + dx, y + dy) not in cells:
            return True
    return False


def _rgb_css(rgb: Tuple[int, int, int], alpha: float = 1.0) -> str:
    r, g, b = rgb
    if alpha >= 1.0:
        return f"rgb({r},{g},{b})"
    return f"rgba({r},{g},{b},{alpha:.3f})"


def _voxel_cube_svg(
    gx: int,
    gy: int,
    size: int,
    *,
    top: str,
    front: str,
    side: str,
) -> str:
    """Render one 3D voxel cube as stacked SVG rects."""
    x = gx * size
    y = gy * size
    face = size - 1
    side_w = max(1, size // 3 + 1)
    depth_h = max(1, size // 3 + 1)
    return (
        f'<rect x="{x + side_w}" y="{y + depth_h}" width="{face}" height="{face}" fill="{front}"/>'
        f'<rect x="{x}" y="{y}" width="{face}" height="{face}" fill="{top}"/>'
        f'<rect x="{x + face}" y="{y + 1}" width="{side_w}" height="{face}" fill="{side}"/>'
        f'<rect x="{x + 1}" y="{y + face}" width="{face}" height="{depth_h}" fill="{side}"/>'
    )


def _build_cursor_svg() -> bytes:
    """Assemble a blue voxel cursor SVG with depth and a soft drop shadow."""
    cells, grid_w, grid_h = _voxel_cells_from_rows(_VOXEL_ROWS)
    size = VOXEL_SIZE
    depth_px = _VOXEL_DEPTH * size

    body_w = grid_w * size + depth_px
    body_h = grid_h * size + depth_px
    shadow_off = max(2, size // 2)
    vb_w = body_w + shadow_off
    vb_h = body_h + shadow_off

    global _VB_X, _VB_Y, _VB_W, _VB_H, _ARROW_FRAC
    _VB_X, _VB_Y = _TIP_SVG_X, _TIP_SVG_Y
    _VB_W, _VB_H = float(vb_w), float(vb_h)
    _ARROW_FRAC = body_h / vb_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_VB_X} {_VB_Y} {_VB_W} {_VB_H}">',
    ]

    shadow_fill = _rgb_css(CURSOR_SHADOW, CURSOR_SHADOW_ALPHA / 255.0)
    for gx, gy in sorted(cells, key=lambda c: (c[1], c[0])):
        sx = gx * size + shadow_off
        sy = gy * size + shadow_off
        parts.append(
            f'<rect x="{sx}" y="{sy}" width="{size}" height="{size}" fill="{shadow_fill}"/>'
        )

    depth_fill = _rgb_css(CURSOR_DEPTH)
    for gx, gy in sorted(cells, key=lambda c: (c[0] + c[1], c[1], c[0])):
        parts.append(
            f'<rect x="{(gx + _VOXEL_DEPTH) * size}" y="{(gy + _VOXEL_DEPTH) * size}"'
            f' width="{size}" height="{size}" fill="{depth_fill}"/>'
        )

    for gx, gy in sorted(cells, key=lambda c: (c[0] + c[1], c[1], c[0])):
        border = _voxel_is_border(gx, gy, cells)
        top = _rgb_css(CURSOR_OUTLINE if border else CURSOR_TOP)
        front = _rgb_css(CURSOR_OUTLINE if border else CURSOR_COLOR, 0.94 if not border else 1.0)
        side = _rgb_css(CURSOR_SIDE if border else CURSOR_INNER_SIDE)
        parts.append(_voxel_cube_svg(gx, gy, size, top=top, front=front, side=side))

    parts.append("</svg>")
    return "".join(parts).encode("utf-8")


_CURSOR_SVG_BYTES: bytes = _build_cursor_svg()
_cached_renderer: Optional[QSvgRenderer] = None


def _get_renderer() -> QSvgRenderer:
    """Return a module-cached QSvgRenderer (created lazily)."""
    global _cached_renderer
    if _cached_renderer is None:
        _cached_renderer = QSvgRenderer(QByteArray(_CURSOR_SVG_BYTES))
    return _cached_renderer

# ── Click effect appearance ─────────────────────────────────────────

CLICK_DURATION_MS = 400.0            # how long the click ripple is visible
CLICK_COLOR = (59, 130, 246)         # electric blue (#3b82f6) in RGB
CLICK_COLOR_BGR = (246, 130, 59)     # blue in BGR for OpenCV
CLICK_MAX_RADIUS = 24.0              # max ripple radius (preview, scaled)
CURSOR_SMOOTH_WINDOW_MS = 72.0       # centered smoothing window for exported cursor motion


def _interp_mouse(track: List[MousePosition], time_ms: float) -> Optional[Tuple[float, float]]:
    """Interpolate mouse position at *time_ms* from recorded track.

    Returns (x, y) in absolute screen coordinates, or None if no data.
    """
    if not track:
        return None
    if time_ms <= track[0].timestamp:
        return track[0].x, track[0].y
    if time_ms >= track[-1].timestamp:
        return track[-1].x, track[-1].y

    # Binary search for the right interval
    lo, hi = 0, len(track) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if track[mid].timestamp <= time_ms:
            lo = mid
        else:
            hi = mid

    a, b = track[lo], track[hi]
    dt = b.timestamp - a.timestamp
    if dt <= 0:
        return a.x, a.y
    t = (time_ms - a.timestamp) / dt
    return a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t


def _interp_mouse_smooth(
    track: List[MousePosition],
    time_ms: float,
    window_ms: float = CURSOR_SMOOTH_WINDOW_MS,
) -> Optional[Tuple[float, float]]:
    """Interpolate and gently smooth cursor position around *time_ms*.

    The mouse tracker samples at roughly 60 Hz, but tiny timer jitter and
    capture/export frame boundaries can make the rendered cursor vibrate by a
    pixel or two.  A centered triangular window preserves intentional movement
    while removing that high-frequency shake.
    """
    if not track:
        return None
    if window_ms <= 0 or len(track) < 3:
        return _interp_mouse(track, time_ms)

    half_window = window_ms / 2.0

    lo_time = time_ms - half_window
    hi_time = time_ms + half_window
    lo = 0
    hi = len(track)
    while lo < hi:
        mid = (lo + hi) // 2
        if track[mid].timestamp < lo_time:
            lo = mid + 1
        else:
            hi = mid
    start = lo

    lo = start
    hi = len(track)
    while lo < hi:
        mid = (lo + hi) // 2
        if track[mid].timestamp <= hi_time:
            lo = mid + 1
        else:
            hi = mid
    end = lo

    if end - start < 2:
        return _interp_mouse(track, time_ms)

    weighted_x = 0.0
    weighted_y = 0.0
    total_weight = 0.0
    for sample in track[start:end]:
        dist = abs(sample.timestamp - time_ms)
        weight = max(0.0, 1.0 - (dist / half_window))
        weighted_x += sample.x * weight
        weighted_y += sample.y * weight
        total_weight += weight

    if total_weight <= 0.0:
        return _interp_mouse(track, time_ms)
    return weighted_x / total_weight, weighted_y / total_weight


# ── Zoom transition cursor flair ────────────────────────────────────


def _cursor_transition_transform(
    phase: Optional[str],
    progress: float,
    cursor_size: float,
) -> Tuple[float, float, float, float, float]:
    """Map a zoom transition to cursor transform around the hotspot.

    Returns ``(scale_x, scale_y, rotation_deg, offset_x, offset_y)``.
    Enter transitions flip horizontally; exit transitions wave/wiggle.
    """
    if not phase or progress >= 1.0:
        return 1.0, 1.0, 0.0, 0.0, 0.0

    t = ease_in_out(progress)

    if phase == "enter":
        scale_x = math.cos(math.pi * t)
        return scale_x, 1.0, 0.0, 0.0, 0.0

    if phase == "exit":
        fade = 1.0 - t
        wave = math.sin(t * math.pi * 3.0) * fade
        rot = wave * 18.0
        offset_y = wave * cursor_size * 0.12
        offset_x = math.sin(t * math.pi * 2.0) * cursor_size * 0.06 * fade
        return 1.0, 1.0, rot, offset_x, offset_y

    return 1.0, 1.0, 0.0, 0.0, 0.0


def _warp_cursor_sprite(
    cursor_bgr: np.ndarray,
    cursor_alpha: np.ndarray,
    scale_x: float,
    scale_y: float,
    rotation_deg: float,
    offset_x: float,
    offset_y: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Affine-transform a cursor sprite keeping the hotspot at the top-left."""
    h, w = cursor_bgr.shape[:2]
    angle = math.radians(rotation_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    a = scale_x * cos_a
    b = scale_x * (-sin_a)
    d = scale_y * sin_a
    e = scale_y * cos_a

    corners = np.array(
        [[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]],
        dtype=np.float32,
    )
    m = np.array([[a, b, offset_x], [d, e, offset_y]], dtype=np.float32)
    transformed = corners @ m.T
    min_x = float(np.min(transformed[:, 0]))
    min_y = float(np.min(transformed[:, 1]))
    max_x = float(np.max(transformed[:, 0]))
    max_y = float(np.max(transformed[:, 1]))

    m[0, 2] -= min_x
    m[1, 2] -= min_y
    out_w = max(1, int(math.ceil(max_x - min_x)))
    out_h = max(1, int(math.ceil(max_y - min_y)))

    warped_bgr = cv2.warpAffine(
        cursor_bgr,
        m,
        (out_w, out_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    warped_alpha = cv2.warpAffine(
        cursor_alpha,
        m,
        (out_w, out_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return warped_bgr, warped_alpha


# ── QPainter-based cursor (for live preview) ───────────────────────


def draw_cursor_qpainter(
    painter: QPainter,
    track: List[MousePosition],
    time_ms: float,
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
    zoom_keyframes: Optional[List[ZoomKeyframe]] = None,
) -> None:
    """Draw a cursor on the preview compositor's screen area.

    *monitor_rect* = dict with left/top/width/height of the captured monitor.
    *screen_rect_*  = pixel position of the screen area in painter coordinates.
    """
    pos = _interp_mouse_smooth(track, time_ms)
    if pos is None:
        return

    mx, my = pos
    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)
    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)

    # Normalize to 0-1 within the monitor
    nx = (mx - mon_left) / mon_w
    ny = (my - mon_top) / mon_h

    # Map to screen rect in painter coords
    px = screen_rect_x + nx * screen_rect_w
    py = screen_rect_y + ny * screen_rect_h

    # Cursor size scales with screen rect (desired arrow height)
    cs = max(18.0, screen_rect_h * 0.038)

    # Full SVG render size (arrow + shadow)
    render_h = cs / _ARROW_FRAC
    render_w = render_h * (_VB_W / _VB_H)

    # Hotspot offset in rendered pixels
    hx = _TIP_NX * render_w
    hy = _TIP_NY * render_h

    # Position SVG so the arrow tip aligns with (px, py)
    target = QRectF(px - hx, py - hy, render_w, render_h)

    phase, progress = compute_cursor_transition(zoom_keyframes or [], time_ms)
    scale_x, scale_y, rot, off_x, off_y = _cursor_transition_transform(
        phase, progress, cs,
    )

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    if phase:
        painter.translate(px, py)
        if phase == "enter":
            painter.scale(scale_x, scale_y)
        else:
            painter.rotate(rot)
            painter.translate(off_x, off_y)
        painter.translate(-px, -py)
    _get_renderer().render(painter, target)
    painter.restore()


# ── OpenCV/numpy-based cursor (for export) ─────────────────────────


def _build_cursor_template(height: int) -> Tuple[np.ndarray, np.ndarray]:
    """Pre-render a cursor image + alpha mask at the given pixel height.

    Returns:
        cursor_bgr:   shape (H, W, 3) — BGR colour channels.
        cursor_alpha: shape (H, W)    — single-channel alpha mask (0-255).

    The cursor tip is at pixel (0, 0) in both returned arrays.
    Includes a soft drop shadow for depth.
    """
    h = max(height, 8)

    # Render height covers the full SVG (arrow + shadow)
    render_h = int(h / _ARROW_FRAC) + 1
    render_w = int(render_h * (_VB_W / _VB_H)) + 1

    renderer = QSvgRenderer(QByteArray(_CURSOR_SVG_BYTES))

    img = QImage(render_w, render_h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    renderer.render(p)
    p.end()

    # QImage ARGB32 on little-endian stores bytes as B, G, R, A
    bpl = img.bytesPerLine()
    buf = img.bits()
    raw = np.frombuffer(buf, dtype=np.uint8).reshape(render_h, bpl)
    arr = raw[:, : render_w * 4].reshape(render_h, render_w, 4).copy()

    # The viewBox origin IS the arrow tip, so pixel (0, 0) is already the
    # hotspot — no cropping offset is required.

    cursor_alpha = arr[:, :, 3]

    # Trim right & bottom transparent edges
    rows = np.any(cursor_alpha > 0, axis=1)
    cols = np.any(cursor_alpha > 0, axis=0)
    if not rows.any():
        return np.zeros((1, 1, 3), dtype=np.uint8), np.zeros((1, 1), dtype=np.uint8)
    rmax = np.where(rows)[0][-1]
    cmax = np.where(cols)[0][-1]

    cursor_bgr = arr[: rmax + 1, : cmax + 1, :3].copy()
    cursor_alpha = cursor_alpha[: rmax + 1, : cmax + 1].copy()
    return cursor_bgr, cursor_alpha


def draw_cursor_cv(
    frame_bgr: np.ndarray,
    track: List[MousePosition],
    time_ms: float,
    mon_left: int,
    mon_top: int,
    mon_w: int,
    mon_h: int,
    cursor_bgr: np.ndarray,
    cursor_alpha: np.ndarray,
    zoom_keyframes: Optional[List[ZoomKeyframe]] = None,
) -> None:
    """Draw cursor onto *frame_bgr* in-place.

    *frame_bgr* is the raw video frame (same resolution as monitor).
    The cursor template is pre-built via _build_cursor_template().
    """
    pos = _interp_mouse_smooth(track, time_ms)
    if pos is None:
        return

    mx, my = pos
    fh, fw = frame_bgr.shape[:2]

    phase, progress = compute_cursor_transition(zoom_keyframes or [], time_ms)
    scale_x, scale_y, rot, off_x, off_y = _cursor_transition_transform(
        phase, progress, float(cursor_bgr.shape[0]),
    )
    sprite_bgr = cursor_bgr
    sprite_alpha = cursor_alpha
    if phase:
        sprite_bgr, sprite_alpha = _warp_cursor_sprite(
            cursor_bgr,
            cursor_alpha,
            scale_x,
            scale_y,
            rot,
            off_x,
            off_y,
        )

    ch, cw = sprite_bgr.shape[:2]

    # Position in frame pixels
    px = int((mx - mon_left) / max(mon_w, 1) * fw)
    py = int((my - mon_top) / max(mon_h, 1) * fh)

    # Bounds check
    x1, y1 = px, py
    x2, y2 = px + cw, py + ch

    # Clip to frame
    src_x1 = max(0, -x1)
    src_y1 = max(0, -y1)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(fw, x2)
    y2 = min(fh, y2)
    src_x2 = src_x1 + (x2 - x1)
    src_y2 = src_y1 + (y2 - y1)

    if x2 <= x1 or y2 <= y1:
        return

    roi = frame_bgr[y1:y2, x1:x2]
    c_roi = sprite_bgr[src_y1:src_y2, src_x1:src_x2]
    a_roi = sprite_alpha[src_y1:src_y2, src_x1:src_x2]

    alpha = a_roi[:, :, np.newaxis].astype(np.float32) / 255.0
    blended = (c_roi.astype(np.float32) * alpha + roi.astype(np.float32) * (1 - alpha))
    np.copyto(roi, blended.astype(np.uint8))


# ── QPainter-based click effects (for live preview) ────────────────


def draw_clicks_qpainter(
    painter: QPainter,
    click_events: List[ClickEvent],
    time_ms: float,
    monitor_rect: dict,
    screen_rect_x: float,
    screen_rect_y: float,
    screen_rect_w: float,
    screen_rect_h: float,
    preset: Optional[ClickEffectPreset] = None,
) -> None:
    """Draw click effects for recent clicks on the preview.

    Supported styles:
    - ``"ripple"`` (default): expanding ring + solid inner dot.
    - ``"burst"``: radiating lines from click point.
    - ``"highlight"``: filled circle that fades out.
    """
    if not click_events:
        return

    if preset is None:
        preset = DEFAULT_CLICK_EFFECT

    # Invisible preset or zero alpha — skip drawing
    if preset.color[3] == 0 or preset.duration_ms <= 0:
        return

    mon_w = max(monitor_rect.get("width", 1), 1)
    mon_h = max(monitor_rect.get("height", 1), 1)
    mon_left = monitor_rect.get("left", 0)
    mon_top = monitor_rect.get("top", 0)

    # Scale radius with preview size
    max_r = max(preset.radius, screen_rect_h * 0.025)
    style = preset.style if preset.style in ("ripple", "burst", "highlight") else "ripple"

    for click in click_events:
        age = time_ms - click.timestamp
        if age < 0 or age > preset.duration_ms:
            continue

        t = age / preset.duration_ms  # 0 → 1

        # Map click position to screen rect
        nx = (click.x - mon_left) / mon_w
        ny = (click.y - mon_top) / mon_h
        px = screen_rect_x + nx * screen_rect_w
        py = screen_rect_y + ny * screen_rect_h

        if style == "burst":
            _draw_burst_qpainter(painter, px, py, t, max_r, preset)
        elif style == "highlight":
            _draw_highlight_qpainter(painter, px, py, t, max_r, preset)
        else:
            _draw_ripple_qpainter(painter, px, py, t, max_r, preset)



def _draw_ripple_qpainter(
    painter: QPainter, px: float, py: float, t: float,
    max_r: float, preset: "ClickEffectPreset",
) -> None:
    """Expanding ring + inner dot (default click style)."""
    radius = max_r * (0.3 + 0.7 * t)
    ring_alpha = int(preset.color[3] * (1.0 - t))
    if ring_alpha > 0:
        color = QColor(preset.color[0], preset.color[1], preset.color[2], ring_alpha)
        pen_w = max(2.0, 3.0 * (1.0 - t))
        painter.setPen(QPen(color, pen_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(px, py), radius, radius)
    dot_alpha = int(preset.color[3] * 0.9 * max(0.0, 1.0 - t * 1.8))
    if dot_alpha > 0:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(preset.color[0], preset.color[1], preset.color[2], dot_alpha))
        dot_r = max(3.0, 5.0 * (1.0 - t * 0.5))
        painter.drawEllipse(QPointF(px, py), dot_r, dot_r)


def _draw_burst_qpainter(
    painter: QPainter, px: float, py: float, t: float,
    max_r: float, preset: "ClickEffectPreset",
) -> None:
    """Radiating lines from click point."""
    num_rays = 8
    ray_alpha = int(preset.color[3] * (1.0 - t))
    if ray_alpha <= 0:
        return
    color = QColor(preset.color[0], preset.color[1], preset.color[2], ray_alpha)
    pen_w = max(1.5, 2.5 * (1.0 - t))
    painter.setPen(QPen(color, pen_w))
    inner_r = max_r * 0.2 * (1.0 + t)
    outer_r = max_r * (0.4 + 0.8 * t)
    for i in range(num_rays):
        angle = 2.0 * math.pi * i / num_rays
        x1 = px + math.cos(angle) * inner_r
        y1 = py + math.sin(angle) * inner_r
        x2 = px + math.cos(angle) * outer_r
        y2 = py + math.sin(angle) * outer_r
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _draw_highlight_qpainter(
    painter: QPainter, px: float, py: float, t: float,
    max_r: float, preset: "ClickEffectPreset",
) -> None:
    """Filled circle that fades out."""
    radius = max_r * 0.8
    fill_alpha = int(preset.color[3] * 0.5 * (1.0 - t))
    if fill_alpha <= 0:
        return
    color = QColor(preset.color[0], preset.color[1], preset.color[2], fill_alpha)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(QPointF(px, py), radius, radius)


# ── OpenCV/numpy-based click effects (for export) ──────────────────


def draw_clicks_cv(
    frame_bgr: np.ndarray,
    click_events: List[ClickEvent],
    time_ms: float,
    mon_left: int,
    mon_top: int,
    mon_w: int,
    mon_h: int,
    preset: Optional[ClickEffectPreset] = None,
) -> None:
    """Draw click effects onto *frame_bgr* in-place.

    Supported styles:
    - ``"ripple"`` (default): expanding ring + solid inner dot.
    - ``"burst"``: radiating lines from click point.
    - ``"highlight"``: filled circle that fades out.
    """
    if not click_events:
        return

    if preset is None:
        preset = DEFAULT_CLICK_EFFECT

    # Invisible preset or zero alpha — skip drawing
    if preset.color[3] == 0 or preset.duration_ms <= 0:
        return

    fh, fw = frame_bgr.shape[:2]
    max_r = max(preset.radius, int(fh * 0.025))

    # Convert RGB to BGR for OpenCV
    color_bgr = (preset.color[2], preset.color[1], preset.color[0])
    base_alpha = preset.color[3] / 255.0
    style = preset.style if preset.style in ("ripple", "burst", "highlight") else "ripple"

    # Use binary search to limit iteration to clicks in the visible window
    window_start = time_ms - preset.duration_ms
    lo = bisect.bisect_left(click_events, window_start, key=lambda c: c.timestamp)
    hi = bisect.bisect_right(click_events, time_ms, key=lambda c: c.timestamp)

    for click in click_events[lo:hi]:
        age = time_ms - click.timestamp
        if age < 0 or age > preset.duration_ms:
            continue

        t = age / preset.duration_ms

        # Position in frame pixels
        px = int((click.x - mon_left) / max(mon_w, 1) * fw)
        py = int((click.y - mon_top) / max(mon_h, 1) * fh)

        if style == "burst":
            _draw_burst_cv(frame_bgr, px, py, t, max_r, color_bgr, base_alpha)
        elif style == "highlight":
            _draw_highlight_cv(frame_bgr, px, py, t, max_r, color_bgr, base_alpha)
        else:
            _draw_ripple_cv(frame_bgr, px, py, t, max_r, color_bgr, base_alpha)


def _draw_ripple_cv(
    frame_bgr: np.ndarray, px: int, py: int, t: float,
    max_r: int, color_bgr: tuple, base_alpha: float,
) -> None:
    """Expanding ring + inner dot (default click style)."""
    radius = int(max_r * (0.3 + 0.7 * t))
    ring_alpha = base_alpha * (1.0 - t)
    if ring_alpha > 0.05:
        thickness = max(1, int(3.0 * (1.0 - t)))
        color_scaled = tuple(int(c * ring_alpha * 0.85) for c in color_bgr)
        cv2.circle(frame_bgr, (px, py), radius, color_scaled, thickness, cv2.LINE_AA)
    dot_alpha = base_alpha * max(0.0, 1.0 - t * 1.8)
    if dot_alpha > 0.05:
        dot_r = max(2, int(5.0 * (1.0 - t * 0.5)))
        color_dot = tuple(int(c * dot_alpha * 0.8) for c in color_bgr)
        cv2.circle(frame_bgr, (px, py), dot_r, color_dot, -1, cv2.LINE_AA)


def _draw_burst_cv(
    frame_bgr: np.ndarray, px: int, py: int, t: float,
    max_r: int, color_bgr: tuple, base_alpha: float,
) -> None:
    """Radiating lines from click point."""
    num_rays = 8
    ray_alpha = base_alpha * (1.0 - t)
    if ray_alpha < 0.05:
        return
    thickness = max(1, int(2.5 * (1.0 - t)))
    color_scaled = tuple(int(c * ray_alpha * 0.85) for c in color_bgr)
    inner_r = max_r * 0.2 * (1.0 + t)
    outer_r = max_r * (0.4 + 0.8 * t)
    for i in range(num_rays):
        angle = 2.0 * math.pi * i / num_rays
        x1 = int(px + math.cos(angle) * inner_r)
        y1 = int(py + math.sin(angle) * inner_r)
        x2 = int(px + math.cos(angle) * outer_r)
        y2 = int(py + math.sin(angle) * outer_r)
        cv2.line(frame_bgr, (x1, y1), (x2, y2), color_scaled, thickness, cv2.LINE_AA)


def _draw_highlight_cv(
    frame_bgr: np.ndarray, px: int, py: int, t: float,
    max_r: int, color_bgr: tuple, base_alpha: float,
) -> None:
    """Filled circle that fades out."""
    radius = int(max_r * 0.8)
    fill_alpha = base_alpha * 0.5 * (1.0 - t)
    if fill_alpha < 0.05:
        return
    color_scaled = tuple(int(c * fill_alpha) for c in color_bgr)
    cv2.circle(frame_bgr, (px, py), radius, color_scaled, -1, cv2.LINE_AA)
