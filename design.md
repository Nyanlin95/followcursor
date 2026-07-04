# Design Spec — Windows Screen Recorder + Editor

This document is written for coding agents such as Codex and Cursor. It defines the product, UX, architecture, data model, implementation phases, and acceptance criteria for building a Python-based Windows desktop app that records the screen and provides lightweight editing/export tools.

## 1. Product Summary

Build a Windows app for creators who need to record product demos, tutorials, walkthroughs, app previews, bug reports, and short marketing clips. The app should feel simpler than OBS, more polished than a raw recorder, and faster than a full video editor.

### Core Promise

Record the screen, cursor, clicks, microphone, and optional system audio; then quickly trim, cut, zoom, polish, and export a clean MP4 without leaving the app.

### Product Name Placeholder

Use `ScreenCraft` as the internal working name. Do not hard-code final branding into the architecture.

## 2. Inspiration From Great Apps

Use these apps as reference patterns, not as something to copy visually.

### OBS Studio

Pattern to borrow: a flexible capture model based on scenes and sources. OBS treats screen, window, webcam, image, browser, and other inputs as sources inside scenes. For this app, use a simplified version: one recording session can have screen, mic, system audio, webcam, cursor, and overlays as separate logical sources.

### Camtasia

Pattern to borrow: record multiple inputs as separate editable tracks. Camtasia’s strength is that screen, camera, system audio, and microphone can be edited separately. For this app, the timeline should preserve separate tracks where possible, even if the first MVP exports a flattened MP4.

### Screen Studio

Pattern to borrow: automatic click-focused zooms, polished framing, smooth motion, background padding, cursor emphasis, and creator-friendly defaults. The app should make plain screen recordings look intentional without requiring advanced editing knowledge.

### ShareX

Pattern to borrow: fast capture modes, region selection, hotkeys, lightweight workflow, and quick export. The recording start flow should be quick and practical, not overloaded.

## 3. Target Users

1. Indie app builders recording product demos.
2. Developers recording bug reports or PR walkthroughs.
3. Startup marketers recording app tutorials.
4. Teachers and course creators recording software lessons.
5. Support teams recording reproducible issue clips.

## 4. MVP Scope

### Must Have

- Windows desktop app built primarily in Python.
- Native-feeling GUI.
- Record full screen, selected monitor, selected window, or selected region.
- Record mouse cursor movement.
- Detect and store mouse clicks as metadata.
- Record microphone audio.
- Optional system audio if available through the user’s Windows/FFmpeg device setup.
- Save each recording as a project.
- Open a simple editor after recording.
- Preview video.
- Trim start/end.
- Split clip at playhead.
- Delete selected segment.
- Add automatic zoom around mouse click events.
- Add manual zoom region/keyframe.
- Cursor highlight and click ripple effect.
- Background/frame preset for polished exports.
- Export MP4 using H.264.
- Autosave project file.

### Should Have

- Global hotkeys for start/stop/pause.
- Countdown before recording.
- Pause/resume recording.
- Export presets: 1080p, 1440p, 4K, GIF preview.
- Basic audio volume controls.
- Simple noise gate or normalize option.
- Recent projects screen.
- Crash-safe recovery.

### Later / Not MVP

- Full multi-track non-linear video editing.
- AI captions.
- AI silence removal.
- Cloud upload.
- Collaboration.
- Green-screen webcam removal.
- Multi-scene livestreaming.
- Plugin marketplace.

## 5. Platform and Technical Constraints

- Target OS: Windows 10 and Windows 11.
- Language: Python 3.11+.
- UI: PySide6 / Qt for Python.
- Rendering/capture backend: FFmpeg controlled by Python subprocesses, with optional PyAV/MoviePy helper layers for analysis and effects.
- App packaging: PyInstaller or Nuitka.
- Store all project data locally.
- Avoid requiring admin permission.
- Work offline.
- Treat recordings as private user data.

## 6. Recommended Tech Stack

### UI

- `PySide6` for the desktop interface.
- Qt Graphics View or custom widgets for the timeline.
- `QMediaPlayer` may be used for basic preview, but prefer a custom preview pipeline if precise frame control becomes necessary.

### Capture

Primary approach:

- Use FFmpeg from Python subprocess.
- Use Windows screen capture input through FFmpeg, initially `gdigrab` for reliability.
- Support full desktop, monitor region, selected rectangle, and window capture where possible.

Optional advanced approach:

- Add Windows Graphics Capture later through a native helper, C++ extension, Rust helper, or a Python-accessible wrapper if smoother capture is required.

### Audio

MVP:

- Microphone capture through FFmpeg DirectShow or Python audio library.
- Keep audio and video in the same FFmpeg process when possible.

Fallback:

- Record mic audio as WAV separately.
- Store start timestamps.
- Mux and sync during project import/render.

System audio:

- Treat as optional in MVP because Windows loopback capture can vary by device and FFmpeg build.
- Build device detection UI early so the user can test audio before recording.

### Cursor and Click Metadata

- Use `pynput` or Windows API hooks to track mouse events.
- Store cursor positions and clicks in JSONL with timestamps relative to recording start.
- Do not burn cursor effects into the source video. Keep them editable when possible.

### Video Editing and Rendering

- Use a non-destructive project model.
- Store original capture files unchanged.
- Store edits as timeline instructions.
- Generate render jobs from project JSON.
- Use FFmpeg filter graphs for trim, concat, scale, crop, pad, audio mix, and export.
- Use PyAV or OpenCV frame processing only for effects that are hard to express in FFmpeg, such as smooth animated zoom following cursor movement.

### Packaging

- Bundle FFmpeg binary with the app or provide first-run download/install detection.
- Use PyInstaller first for speed of development.
- Consider Nuitka later if startup time or antivirus false positives become a problem.

## 7. Core UX

## 7.1 Home Screen

Purpose: choose how to start.

Layout:

- Left side: recent projects.
- Center: large capture options.
- Right side: recording settings.

Primary actions:

- Record Full Screen
- Record Window
- Record Region
- Open Project
- Import Video

Settings:

- Monitor/window selector.
- Microphone selector.
- System audio selector if available.
- FPS: 30 or 60.
- Quality: Standard, High, Lossless-ish.
- Cursor visible: on/off.
- Click markers: on/off.
- Countdown: off, 3s, 5s.

## 7.2 Region Selection Overlay

Purpose: fast selection before recording.

Behavior:

- Dim entire desktop.
- User drags a rectangle.
- Show pixel dimensions.
- Snap to windows when hovering if possible.
- Buttons: Start Recording, Cancel.
- Escape cancels.

## 7.3 Recording HUD

Purpose: unobtrusive control.

Design:

- Small floating pill.
- Shows duration, mic level, pause/stop buttons.
- Stays above windows.
- Option to auto-hide.

Controls:

- Start after countdown.
- Pause/resume.
- Stop.
- Hotkeys:
  - Start/stop: Ctrl+Shift+R
  - Pause/resume: Ctrl+Shift+P
  - Add marker: Ctrl+Shift+M

## 7.4 Post-Recording Import

After stopping:

1. Save raw recording.
2. Save metadata.
3. Generate low-resolution proxy if needed.
4. Open editor with project loaded.

Show a progress state if proxy generation is needed.

## 7.5 Editor Screen

Use a familiar video editor layout:

- Top left: media/project panel.
- Center: preview canvas.
- Right: inspector/properties panel.
- Bottom: timeline.

### Preview Canvas

Must support:

- Play/pause.
- Scrub.
- Fit/fill preview.
- Show export frame.
- Show crop/zoom rectangles.
- Show cursor effects.

### Timeline

Tracks:

1. Screen video track.
2. Cursor/click metadata track.
3. Microphone audio track.
4. System audio track.
5. Effects/zoom track.
6. Optional overlay track later.

Minimum interactions:

- Click to move playhead.
- Drag clip edges to trim.
- Split at playhead.
- Delete selected segment.
- Zoom in/out timeline.
- Undo/redo edits.

### Inspector

When nothing is selected:

- Project name.
- Canvas size.
- Export preset.
- Background preset.

When a video clip is selected:

- Start/end.
- Speed.
- Volume if clip has audio.
- Crop.

When a zoom effect is selected:

- Start time.
- End time.
- Zoom target rectangle.
- Scale amount.
- Easing.

When cursor effect is selected:

- Cursor visible.
- Highlight radius.
- Click ripple on/off.
- Click sound on/off.

## 8. Visual Design Direction

### General Feeling

- Clean, modern, technical, creator-focused.
- More like a polished productivity tool than a heavy pro editor.
- Use dark mode as default.
- Avoid clutter.
- Make primary actions obvious.

### UI Style

- Dark graphite background.
- Soft panels.
- Rounded corners.
- Subtle borders.
- High-contrast text.
- Accent color: electric blue or lime green.
- Timeline should be calm and readable.

### Preview Export Styles

Built-in presets:

1. Clean Screen: no background, direct screen capture.
2. Soft Frame: rounded screen frame with shadow.
3. Gradient Stage: screen centered on gradient background.
4. Tutorial Focus: auto zoom + cursor highlight enabled.
5. Social Clip: 9:16, 1:1, and 4:5 canvas options.

## 9. Recording Data Model

Every recording becomes a project folder.

```text
projects/
  <project_id>/
    project.json
    captures/
      screen_original.mp4
      mic.wav
      system_audio.wav
    metadata/
      cursor.jsonl
      clicks.jsonl
      markers.jsonl
      devices.json
    proxies/
      screen_proxy.mp4
      waveform_mic.json
      waveform_system.json
    renders/
      export_001.mp4
```

## 10. Project JSON Schema

Use this shape as the first version. Keep it readable and migration-friendly.

```json
{
  "schema_version": 1,
  "project_id": "2026-07-03_1530_demo",
  "name": "Untitled Recording",
  "created_at": "2026-07-03T15:30:00+07:00",
  "source": {
    "screen_file": "captures/screen_original.mp4",
    "mic_file": "captures/mic.wav",
    "system_audio_file": null,
    "cursor_file": "metadata/cursor.jsonl",
    "clicks_file": "metadata/clicks.jsonl",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration": 74.35
  },
  "canvas": {
    "width": 1920,
    "height": 1080,
    "background": {
      "type": "solid",
      "color": "#111318"
    },
    "screen_frame": {
      "enabled": true,
      "corner_radius": 18,
      "shadow": true,
      "padding": 72
    }
  },
  "timeline": {
    "clips": [
      {
        "id": "clip_001",
        "source": "screen_file",
        "source_in": 0.0,
        "source_out": 74.35,
        "timeline_in": 0.0,
        "timeline_out": 74.35,
        "enabled": true
      }
    ],
    "audio_tracks": [
      {
        "id": "mic_track",
        "source": "mic_file",
        "volume": 1.0,
        "muted": false
      }
    ],
    "effects": [
      {
        "id": "zoom_001",
        "type": "zoom",
        "start": 12.4,
        "end": 16.2,
        "target": { "x": 820, "y": 410, "width": 480, "height": 270 },
        "scale": 1.6,
        "easing": "ease_in_out"
      }
    ]
  },
  "cursor": {
    "visible": true,
    "highlight_enabled": true,
    "highlight_radius": 34,
    "click_ripple_enabled": true
  },
  "export": {
    "format": "mp4",
    "codec": "h264",
    "preset": "high_quality_1080p",
    "fps": 30,
    "audio_bitrate": "192k"
  }
}
```

## 11. Cursor and Click Metadata

### Cursor JSONL

Each line:

```json
{"t": 0.033, "x": 932, "y": 510, "visible": true}
```

### Click JSONL

Each line:

```json
{"t": 12.412, "x": 1042, "y": 622, "button": "left", "event": "down"}
```

Use timestamps relative to recording start, not wall-clock time.

## 12. Auto Zoom Logic

Auto zoom should make recordings easier to follow without making the user feel seasick.

### Rule Set

1. Detect click clusters.
2. Ignore clicks that happen too close together unless they are in different areas.
3. Create zoom events around important clicks.
4. Use smooth easing.
5. Hold zoom briefly after the click.
6. Return to full view before the next unrelated action.

### Suggested Defaults

- Zoom start: 0.25s before click.
- Zoom hold: 1.2s after click.
- Zoom scale: 1.4x to 1.8x.
- Max zoom scale: 2.2x.
- Minimum time between zooms: 1.0s.
- Easing: cubic ease in/out.

### Auto Zoom Pseudocode

```python
def generate_auto_zoom_events(clicks, screen_width, screen_height):
    events = []
    last_event = None

    for click in clicks:
        if click["event"] != "down":
            continue

        if last_event and click["t"] - last_event["end"] < 1.0:
            distance = ((click["x"] - last_event["cx"]) ** 2 + (click["y"] - last_event["cy"]) ** 2) ** 0.5
            if distance < 240:
                continue

        target_width = screen_width * 0.45
        target_height = screen_height * 0.45
        x = clamp(click["x"] - target_width / 2, 0, screen_width - target_width)
        y = clamp(click["y"] - target_height / 2, 0, screen_height - target_height)

        event = {
            "type": "zoom",
            "start": max(0, click["t"] - 0.25),
            "end": click["t"] + 1.2,
            "target": {"x": x, "y": y, "width": target_width, "height": target_height},
            "scale": 1.6,
            "easing": "ease_in_out",
            "cx": click["x"],
            "cy": click["y"]
        }
        events.append(event)
        last_event = event

    return events
```

## 13. Rendering Pipeline

Rendering should be deterministic and resumable.

### Render Steps

1. Load project JSON.
2. Validate source files exist.
3. Build timeline segments from clips and cuts.
4. Apply visual effects:
   - trim
   - crop
   - scale
   - pad/background
   - cursor highlight
   - click ripple
   - zooms
5. Mix audio tracks.
6. Encode output MP4.
7. Write render report.

### Render Report

Save next to exports:

```json
{
  "export_file": "renders/export_001.mp4",
  "started_at": "2026-07-03T15:45:00+07:00",
  "finished_at": "2026-07-03T15:45:31+07:00",
  "duration_seconds": 31.4,
  "ffmpeg_command": "...",
  "warnings": []
}
```

## 14. App Architecture

Use a modular architecture. Keep UI, project state, recording, and rendering separated.

```text
app/
  main.py
  config.py
  ui/
    main_window.py
    home_screen.py
    recorder_overlay.py
    region_selector.py
    editor_window.py
    timeline_widget.py
    preview_widget.py
    inspector_panel.py
  core/
    project.py
    project_schema.py
    autosave.py
    paths.py
    events.py
  capture/
    ffmpeg_capture.py
    device_discovery.py
    cursor_tracker.py
    hotkeys.py
  editor/
    timeline_model.py
    edit_commands.py
    auto_zoom.py
    waveform.py
  render/
    render_job.py
    ffmpeg_builder.py
    export_presets.py
    render_worker.py
  utils/
    logging.py
    timecode.py
    easing.py
    validation.py
  tests/
    test_project_schema.py
    test_timeline_model.py
    test_auto_zoom.py
    test_ffmpeg_builder.py
```

## 15. Key Modules

### `core/project.py`

Responsibilities:

- Create project folder.
- Load/save `project.json`.
- Validate schema version.
- Resolve relative paths.
- Autosave edits.
- Support future schema migrations.

### `capture/ffmpeg_capture.py`

Responsibilities:

- Build FFmpeg capture command.
- Start/stop FFmpeg process.
- Monitor stderr for errors.
- Emit status events to UI.
- Handle pause/resume if supported; otherwise split recording into segments and merge later.

### `capture/device_discovery.py`

Responsibilities:

- List monitors.
- List windows.
- List microphones.
- List available system audio options.
- Provide a test-record function.

### `capture/cursor_tracker.py`

Responsibilities:

- Track mouse coordinates.
- Track clicks.
- Write JSONL files.
- Use monotonic clock aligned with recording start.

### `editor/timeline_model.py`

Responsibilities:

- Represent clips, cuts, and effects.
- Split clips.
- Delete ranges.
- Ripple timeline after deletion.
- Convert timeline to render segments.

### `editor/auto_zoom.py`

Responsibilities:

- Parse click metadata.
- Generate suggested zoom events.
- Allow user to accept, regenerate, or delete.

### `render/ffmpeg_builder.py`

Responsibilities:

- Convert project JSON to FFmpeg commands.
- Escape paths correctly on Windows.
- Build filter graphs.
- Support dry-run mode for tests.

### `render/render_worker.py`

Responsibilities:

- Run render jobs off the UI thread.
- Track progress.
- Allow cancel.
- Save render report.

## 16. State Management

Use a central project state object. UI should not directly mutate JSON.

Pattern:

1. UI dispatches command.
2. Command modifies timeline model.
3. State emits change event.
4. UI updates.
5. Autosave writes project JSON.

Example commands:

- `TrimClipCommand`
- `SplitClipCommand`
- `DeleteRangeCommand`
- `AddZoomCommand`
- `UpdateZoomCommand`
- `ToggleCursorHighlightCommand`

Support undo/redo by making commands reversible.

## 17. Error Handling

Common errors and required UX:

### FFmpeg Missing

Message:

> FFmpeg is required for recording and export. Install it or choose a bundled version.

Actions:

- Locate FFmpeg
- Download / install later
- Cancel

### Audio Device Missing

Message:

> The selected microphone is unavailable. Choose another input or record without microphone.

Actions:

- Choose device
- Record without mic

### Capture Failed

Message:

> Recording could not start. Check screen permissions, selected window, and audio devices.

Also show technical details in expandable log.

### Render Failed

Message:

> Export failed. Your project is safe. Review the render log or try another preset.

Actions:

- Open log
- Retry
- Change preset

## 18. Performance Requirements

MVP target:

- Record 1080p at 30 FPS reliably on average Windows laptops.
- Record 1080p at 60 FPS on stronger machines.
- Editor should remain responsive while generating proxies.
- Timeline scrub should use proxy video if original is heavy.
- Export should run in background thread/process.

Optimization strategies:

- Use proxy files for editing.
- Avoid loading full video into memory.
- Use streaming reads/writes.
- Use FFmpeg hardware encoding if available later.
- Cache waveform and cursor data.

## 19. Accessibility and Usability

- Keyboard shortcuts for all core actions.
- Clear focus states.
- Tooltips for technical settings.
- Avoid tiny timeline handles.
- Provide readable contrast in dark mode.
- Use plain language for recording/export errors.

## 20. Security and Privacy

- Do not upload recordings.
- Do not phone home in MVP.
- Store all projects locally.
- Never record before explicit user action.
- Show visible recording indicator.
- Stop all capture hooks when recording ends.
- Do not log sensitive file paths unless needed for debugging.

## 21. Implementation Phases

## Phase 0 — Repo Setup

Goal: create a clean, runnable Python desktop app skeleton.

Tasks:

- Create project structure.
- Add PySide6 main window.
- Add config and logging.
- Add basic home screen.
- Add dependency management with `pyproject.toml`.
- Add test setup with `pytest`.

Acceptance criteria:

- `python -m app.main` opens the app.
- Tests run.
- App has Home, Record, and Open Project placeholder buttons.

## Phase 1 — Basic Screen Recording

Goal: record full screen to MP4.

Tasks:

- Detect FFmpeg.
- Build FFmpeg capture command.
- Add start/stop recording.
- Save recording to project folder.
- Create project JSON.
- Show recording duration.

Acceptance criteria:

- User can record full desktop.
- Stopping creates a playable MP4.
- Project folder contains `project.json` and source file.

## Phase 2 — Region / Window Recording

Goal: support practical capture modes.

Tasks:

- Add monitor list.
- Add region selection overlay.
- Add selected rectangle capture.
- Add window list if feasible.
- Store capture region in project JSON.

Acceptance criteria:

- User can drag a region and record only that region.
- Multi-monitor setup does not crash.
- DPI scaling is handled correctly or clearly warned.

## Phase 3 — Audio and Cursor Metadata

Goal: capture important creator inputs.

Tasks:

- List microphone devices.
- Record mic with video or as separate WAV.
- Track cursor position.
- Track clicks.
- Store cursor/click JSONL.
- Add audio test meter.

Acceptance criteria:

- Recording includes mic audio.
- Clicks are written with accurate timestamps.
- Cursor metadata aligns with the video timeline.

## Phase 4 — Editor MVP

Goal: open project and perform simple edits.

Tasks:

- Build editor layout.
- Add video preview.
- Add basic timeline model.
- Add trim start/end.
- Add split at playhead.
- Add delete selected segment.
- Add undo/redo for edit commands.

Acceptance criteria:

- User can trim and cut a recording.
- Project autosaves edits.
- Reopening project restores timeline state.

## Phase 5 — Export MVP

Goal: render edited timeline to MP4.

Tasks:

- Convert timeline edits to FFmpeg trim/concat command.
- Mix mic audio.
- Add export presets.
- Add render progress UI.
- Save render report.

Acceptance criteria:

- User can export edited video.
- Exported MP4 plays correctly.
- Audio remains in sync.

## Phase 6 — Auto Zoom and Cursor Effects

Goal: make recordings look polished.

Tasks:

- Generate zoom events from click metadata.
- Add zoom effect track.
- Add manual zoom editor.
- Add cursor highlight effect.
- Add click ripple effect.
- Render effects into final MP4.

Acceptance criteria:

- One-click auto zoom creates sensible zooms.
- User can delete or adjust zooms.
- Export contains smooth zooms and cursor emphasis.

## Phase 7 — Polish and Packaging

Goal: ship a usable Windows app.

Tasks:

- Add icons and app metadata.
- Add settings page.
- Add recent projects.
- Add crash recovery.
- Bundle FFmpeg.
- Build installer or portable ZIP.
- Test on clean Windows machine.

Acceptance criteria:

- App launches from packaged build.
- Recording and export work without a Python install.
- App handles missing devices gracefully.

## 22. Coding Standards for Codex/Cursor

When implementing this project:

1. Prefer small, testable modules.
2. Do not put capture/render logic inside UI widgets.
3. Use type hints everywhere practical.
4. Use dataclasses or Pydantic-style validation for project data.
5. Keep file paths relative inside `project.json`.
6. Never overwrite source recordings.
7. Add tests for timeline and render command logic before UI polish.
8. Keep FFmpeg commands logged for debugging.
9. Use worker threads/processes for long-running tasks.
10. Avoid blocking the Qt main thread.

## 23. Suggested Dependencies

Initial dependencies:

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "PySide6",
  "pynput",
  "pydantic",
  "platformdirs",
  "numpy",
  "pytest"
]
```

Optional later dependencies:

```toml
[project.optional-dependencies]
media = [
  "av",
  "moviepy",
  "opencv-python",
  "sounddevice",
  "soundfile"
]
package = [
  "pyinstaller"
]
```

Do not add heavy dependencies until a phase actually needs them.

## 24. First Implementation Prompt for Codex/Cursor

Use this prompt to start the build:

```text
Read design.md carefully. Implement Phase 0 only. Create a Python 3.11+ PySide6 app skeleton with the project structure from the spec. The app should launch with a Home screen containing buttons for Record Full Screen, Record Region, Open Project, and Settings. Add logging, config, and pytest setup. Do not implement recording yet. Keep modules small and typed. After implementation, explain the files created and how to run tests.
```

## 25. Second Implementation Prompt

```text
Read design.md and the existing code. Implement Phase 1: basic full-screen recording using FFmpeg controlled by Python. Add FFmpeg detection, a start/stop recording flow, project folder creation, and project.json generation. Keep capture logic outside UI widgets. Add tests for FFmpeg command generation and project creation. Do not implement region selection yet.
```

## 26. Third Implementation Prompt

```text
Read design.md and the existing code. Implement Phase 2: region recording. Add a transparent/dimmed region selector overlay, save selected rectangle coordinates, pass them to FFmpeg capture, and store capture metadata in project.json. Handle DPI scaling carefully on Windows. Add tests where possible for region coordinate normalization.
```

## 27. Known Risks

### Python Screen Recording Performance

Pure Python frame capture may struggle for high-FPS recording. Prefer FFmpeg for actual capture and use Python as controller/orchestrator.

### Audio Sync

Separate audio and video capture can drift. Prefer one FFmpeg process when possible, or store exact timestamps and mux carefully.

### Windows DPI Scaling

Region selection can be wrong on high-DPI displays. Set DPI awareness early and test 100%, 125%, and 150% scaling.

### System Audio

Loopback recording varies by machine and FFmpeg build. Make it optional in MVP.

### Smooth Auto Zoom

Dynamic animated zoom can become complex in FFmpeg. Start with simpler zoom segments; improve with a frame processing pipeline later.

## 28. Definition of Done for MVP

The MVP is done when a user can:

1. Launch the Windows app.
2. Select full screen or region.
3. Record screen + microphone.
4. Stop recording.
5. Open the recording in the editor.
6. Trim, split, and delete parts.
7. Add automatic click zooms.
8. Export a polished MP4.
9. Reopen the project later and continue editing.

## 29. Future Feature Ideas

- Webcam bubble with drag-to-position.
- Speaker notes/prompter mode.
- Auto captions.
- Silence removal.
- Background music.
- Brand presets.
- Cursor smoothing.
- Click sound library.
- Export directly to YouTube Shorts/TikTok formats.
- Shareable compressed bug report mode.
- AI summary of recording.
- Template-based product demo generator.

## 30. Design Principle

The app should not try to become a professional editor first. It should first become the fastest way to make a screen recording look clean, focused, and useful.
