# Fork lineage and custom changes

This repository is a **personal fork** of the upstream FollowCursor project. It keeps the same core recording and export pipeline, but tracks a separate `main` branch with UI and cursor polish that is maintained independently.

| Repository | URL | Role |
| ---------- | --- | ---- |
| **Upstream (original)** | [github.com/sabbour/followcursor](https://github.com/sabbour/followcursor) | Source project, releases, and documentation site |
| **This fork** | [github.com/Nyanlin95/followcursor](https://github.com/Nyanlin95/followcursor) | Personal working copy with custom UI and cursor work |

## Git remotes (local clone)

```text
origin   → https://github.com/Nyanlin95/followcursor.git   (this fork)
upstream → https://github.com/sabbour/followcursor.git      (original)
```

Pull upstream fixes when needed:

```powershell
git fetch upstream
git merge upstream/main
```

Then resolve conflicts, run tests, and push to `origin`.

---

## Upstream (original project)

Credit and canonical docs belong to the upstream repo:

- Windows screen/window recording (WGC + ffmpeg)
- Smart auto-zoom and AI zoom / narration / chapters
- Timeline editor, trim, split, voiceover tracks
- Cinematic export (H.264 / GIF, GPU encoders)
- `.fcproj` project bundles
- Architecture described in [ARCHITECTURE.md](ARCHITECTURE.md) and the [user guide](USER_GUIDE.md)

Do **not** treat this fork as the official release channel unless you explicitly intend to.

---

## This fork (custom redoing)

Changes below are **fork-specific** and may diverge from upstream. They are not guaranteed to be merged back.

### Cursor overlay

| Feature | Description |
| ------- | ----------- |
| **Blue voxel pointer** | Block-style 3D cursor (electric-blue palette) instead of the flat white arrow |
| **Zoom-in flair** | Horizontal **flip** while the camera zooms in (during the keyframe transition only) |
| **Zoom-out flair** | Gentle **wave** (rotation + offset) while the camera zooms out |
| **Steady zoom** | Normal static cursor while fully zoomed in — no flip and wave at the same time |

Implementation: `app/cursor_renderer.py` (`compute_cursor_transition` in `app/zoom_engine.py`).

### UI layout stability

| Feature | Description |
| ------- | ----------- |
| Fixed-width export / discard actions | Title bar buttons no longer shift when export text or discard visibility changes |
| Record / stop slot | Shared fixed-size stack so record ↔ stop does not resize the control bar |
| Editor panel width | Theme and layout aligned to 320px panel width |
| Status bar | Long status text can shrink without overlapping encoder / shortcut labels |
| Focus rings | Removed QSS border/padding focus shifts that caused control size jumps |

### Theme

- Fluent-style tokens and light/dark theme toggle refinements
- Electric blue brand (aligned across cursor, clicks, and accents)

### Tests added on the fork

- `tests/test_cursor_renderer.py` — voxel cursor template + transition transforms
- `tests/test_zoom_engine.py` — `compute_cursor_transition` enter/exit/steady phases

---

## What to report where

| Issue type | Report to |
| ---------- | --------- |
| Core recording, export, AI features, upstream bugs | [sabbour/followcursor issues](https://github.com/sabbour/followcursor/issues) |
| Fork-only cursor flair, UI polish, this fork's `main` | [Nyanlin95/followcursor issues](https://github.com/Nyanlin95/followcursor/issues) |

When contributing a fix that belongs upstream, prefer opening a PR against **sabbour/followcursor** and then merging `upstream/main` into this fork.
