"""FollowCursor — screen recorder with cinematic cursor-following zoom."""

import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QAbstractNativeEventFilter, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.icon import create_app_icon, get_ico_path
from app.main_window import MainWindow
from app.splash_screen import finish_startup_splash, show_startup_splash
from app.theme import get_base_palette
from app.version import __version__

# ── Log file path ───────────────────────────────────────────────────
# Stored in %LOCALAPPDATA%/FollowCursor/error.log so it survives
# across sessions.  Only ERROR and above are written to the file;
# the console handler still shows INFO+.
_LOG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", tempfile.gettempdir()),
    "FollowCursor",
)
os.makedirs(_LOG_DIR, exist_ok=True)
ERROR_LOG_PATH = os.path.join(_LOG_DIR, "error.log")

# ── Console handler (INFO+) ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)

# ── File handler (ERROR+) ──────────────────────────────────────────
_file_handler = RotatingFileHandler(
    ERROR_LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8",
)
_file_handler.setLevel(logging.ERROR)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(name)s | %(levelname)s | %(message)s\n"
    "  File: %(pathname)s:%(lineno)d\n"
    "  Function: %(funcName)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.getLogger().addHandler(_file_handler)

_logger = logging.getLogger(__name__)


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """Log unhandled exceptions instead of crashing silently."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


# Suppress Qt's internal "QFont::setPointSize: Point size <= 0" warnings
# that fire during DPI transitions between monitors with different scale
# factors. All our code uses setPixelSize / font-size: Npx — the -1 comes
# from Qt's stylesheet engine recalculating during the transition.
_original_handler = None


def _message_handler(msg_type, context, message):
    """Custom Qt message handler that suppresses harmless DPI warnings."""
    if "QFont::setPointSize" in message:
        return  # suppress
    if _original_handler:
        _original_handler(msg_type, context, message)
    else:
        # Default: print to stderr like Qt does
        if msg_type != QtMsgType.QtDebugMsg:
            print(message, file=sys.stderr)


class _WinCloseFilter(QAbstractNativeEventFilter):
    """Intercept WM_CLOSE at the application level so taskbar close works
    even when a modal dialog is open."""

    def __init__(self, main_window):
        super().__init__()
        self._main_window = main_window

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                import ctypes, ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0010:  # WM_CLOSE
                    # Close any open modal dialog first (e.g. source picker)
                    modal = QApplication.activeModalWidget()
                    if modal:
                        modal.close()
                    self._main_window.close()
                    return True, 0
            except Exception:
                pass
        return False, 0


def main() -> None:
    """Application entry point — creates QApplication, applies theme, shows MainWindow."""
    sys.excepthook = _global_exception_handler

    # Suppress QFont::setPointSize warnings from Qt's stylesheet DPI recalc
    global _original_handler
    _original_handler = qInstallMessageHandler(_message_handler)

    # Set Windows AppUserModelID so the taskbar uses our icon, not Python's
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "FollowCursor.FollowCursor.1"
        )

    app = QApplication(sys.argv)
    app.setApplicationName("FollowCursor")
    app.setApplicationVersion(__version__)

    # Build QIcon from painted pixmaps (fast QPainter-based icon)
    icon = create_app_icon()
    app.setWindowIcon(icon)

    # Base palette before MainWindow applies the full theme QSS
    app.setPalette(get_base_palette(dark=True))

    splash = show_startup_splash(app, icon, __version__)
    try:
        window = MainWindow()
    except Exception:
        splash.close()
        splash.deleteLater()
        raise

    window.startup_ready.connect(
        lambda: finish_startup_splash(splash, window)
    )
    window.show()

    # Merge the .ico file AFTER the window is visible (saves ~78ms from startup)
    def _load_ico():
        try:
            ico_path = get_ico_path()
            ico_icon = QIcon(ico_path)
            for sz in ico_icon.availableSizes():
                icon.addPixmap(ico_icon.pixmap(sz))
            app.setWindowIcon(icon)
        except Exception:
            pass
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, _load_ico)

    # Install native event filter for taskbar close support
    if sys.platform == "win32":
        close_filter = _WinCloseFilter(window)
        app.installNativeEventFilter(close_filter)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
