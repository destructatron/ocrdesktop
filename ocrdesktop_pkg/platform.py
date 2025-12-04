"""Platform detection and conditional imports for OCRdesktop."""

import os

def detect_display_server():
    """Detect if running on Wayland or X11.

    Returns:
        str: 'wayland', 'x11', or None if unknown
    """
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    if session_type in ('wayland', 'x11'):
        return session_type
    if os.environ.get('WAYLAND_DISPLAY'):
        return 'wayland'
    if os.environ.get('DISPLAY'):
        return 'x11'
    return None


# Detect display server at module load time
display_server = detect_display_server()

# Optional dependency flags
pdf2image_available = True
try:
    from pdf2image import convert_from_path
except ImportError:
    pdf2image_available = False
    convert_from_path = None

scipy_available = True
try:
    from scipy.spatial import KDTree
except ImportError:
    scipy_available = False
    KDTree = None

webcolors_available = True
try:
    from webcolors import CSS2_HEX_TO_NAMES, CSS3_HEX_TO_NAMES, hex_to_rgb
except ImportError:
    webcolors_available = False
    CSS2_HEX_TO_NAMES = None
    CSS3_HEX_TO_NAMES = None
    hex_to_rgb = None

# GTK/GDK imports - these are required
ui_available = True
wnck_available = False
pyatspi = None
Wnck = None

try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GObject, Gio, GLib

    # Wnck is X11-only, skip on Wayland
    if display_server != 'wayland':
        gi.require_version("Wnck", "3.0")
        from gi.repository import Wnck
        wnck_available = True

    # AT-SPI (also X11-only for mouse/keyboard interaction)
    if display_server != 'wayland':
        gi.require_version('Atspi', '2.0')
        import pyatspi
except Exception:
    ui_available = False
    Gtk = None
    Gdk = None
    GObject = None
    Gio = None
    GLib = None
