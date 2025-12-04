"""Screenshot capture functionality for OCRdesktop."""

import os
import tempfile
from urllib.parse import urlparse, unquote
from mimetypes import MimeTypes

from PIL import Image

from .platform import (
    display_server, ui_available, wnck_available,
    pdf2image_available, convert_from_path,
    Gtk, Gdk, Gio, GLib, Wnck
)


def pixbuf_to_image(pix):
    """Convert GdkPixbuf to PIL Image.

    Args:
        pix: GdkPixbuf object

    Returns:
        PIL.Image: Converted image
    """
    data = pix.get_pixels()
    w = pix.props.width
    h = pix.props.height
    stride = pix.props.rowstride
    mode = "RGBA" if pix.props.has_alpha else "RGB"
    return Image.frombytes(mode, (w, h), data, "raw", mode, stride)


class ScreenshotCapture:
    """Handles screenshot capture from various sources."""

    def __init__(self, debug=False):
        self._debug = debug
        self._display_server = display_server
        self._offset_x = 0
        self._offset_y = 0
        self._images = []

    @property
    def images(self):
        """Get captured images."""
        return self._images

    @property
    def offset_x(self):
        """Get X offset of captured window."""
        return self._offset_x

    @property
    def offset_y(self):
        """Get Y offset of captured window."""
        return self._offset_y

    def capture(self, mode, file_path=''):
        """Capture screenshot based on mode.

        Args:
            mode: 0=window, 1=desktop, 2=clipboard, 3=file
            file_path: Path to file (for mode 3)

        Returns:
            bool: True if capture was successful
        """
        if not ui_available:
            if self._debug:
                print('GTK / GDK / GI is not available')
            return False

        if mode == 0:  # Window
            return self._capture_with_fallback()
        elif mode == 1:  # Desktop
            return self._capture_desktop()
        elif mode == 2:  # Clipboard
            return self._capture_clipboard()
        elif mode == 3:  # File
            return self._capture_file(file_path)
        return False

    def _capture_with_fallback(self):
        """Capture window with fallback to desktop."""
        try:
            if self._capture_window():
                return True
            if self._debug:
                print('FALLBACK: was not able to Screenshot active window. Try Rootwindow now')
            return self._capture_desktop()
        except Exception as e:
            if self._debug:
                print(f'FALLBACK: Screenshot window error: {e}')
            return self._capture_desktop()

    def _capture_window(self):
        """Capture the active window."""
        if self._display_server == 'wayland':
            if self._debug:
                print("Wayland detected: using portal for window screenshot (interactive)")
            result = self._capture_portal(interactive=True)
            if not result:
                if self._debug:
                    print("Interactive mode failed, falling back to full screen capture")
                result = self._capture_portal(interactive=False)
            return result

        # X11 path
        Gtk.main_iteration_do(False)  # Workaround for segfault
        gdk_desktop = Gdk.get_default_root_window()

        try:
            wnck_screen = Wnck.Screen.get_default()
            wnck_screen.force_update()
            wnck_window = wnck_screen.get_active_window()
            self._offset_x, self._offset_y, width, height = Wnck.Window.get_geometry(wnck_window)
            pixbuf = Gdk.pixbuf_get_from_window(gdk_desktop, self._offset_x, self._offset_y, width, height)
        except Exception as e:
            if self._debug:
                print(f"error while screenshot window: {e}")
            return False

        if pixbuf is not None:
            self._images = [pixbuf_to_image(pixbuf)]
            if self._debug:
                self._images[0].save("/tmp/ocrScreenshot.png")
                print("save screenshot:/tmp/ocrScreenshot.png")
            return True
        else:
            if self._debug:
                print("Could not take screenshot")
            return False

    def _capture_desktop(self):
        """Capture the entire desktop."""
        if self._display_server == 'wayland':
            if self._debug:
                print("Wayland detected: using portal for desktop screenshot")
            return self._capture_portal(interactive=False)

        # X11 path
        desktop = Gdk.get_default_root_window()
        pixbuf = Gdk.pixbuf_get_from_window(desktop, 0, 0, desktop.get_width(), desktop.get_height())

        if pixbuf is not None:
            self._images = [pixbuf_to_image(pixbuf)]
            if self._debug:
                self._images[0].save("/tmp/ocrScreenshot.png")
                print("save screenshot:/tmp/ocrScreenshot.png")
            return True
        else:
            if self._debug:
                print("Could not take screenshot")
            return False

    def _capture_portal(self, interactive=True):
        """Capture screenshot using XDG Desktop Portal (for Wayland).

        Args:
            interactive: If True, shows selection dialog (for window mode)
                        If False, captures entire screen (for desktop mode)

        Returns:
            bool: True if screenshot was successful
        """
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.Screenshot",
                None
            )

            args = GLib.Variant('(sa{sv})', ('', {
                'interactive': GLib.Variant.new_boolean(interactive),
                'modal': GLib.Variant.new_boolean(True)
            }))

            screenshot_path = None
            loop = GLib.MainLoop()

            def on_response(connection, sender, path, interface, signal, params, user_data):
                nonlocal screenshot_path
                if not isinstance(params, GLib.Variant):
                    if loop.is_running():
                        loop.quit()
                    return

                response_code, results = params.unpack()

                if response_code == 0 and 'uri' in results:
                    parsed = urlparse(results['uri'])
                    if parsed.scheme == 'file':
                        screenshot_path = unquote(parsed.path)
                else:
                    if self._debug:
                        print(f"Portal screenshot failed: code={response_code}")

                if loop.is_running():
                    loop.quit()

            result = proxy.call_sync(
                'Screenshot',
                args,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )

            request_handle = result.unpack()[0]

            subscription_id = bus.signal_subscribe(
                "org.freedesktop.portal.Desktop",
                "org.freedesktop.portal.Request",
                "Response",
                request_handle,
                None,
                Gio.DBusSignalFlags.NO_MATCH_RULE,
                on_response,
                None
            )

            try:
                GLib.timeout_add_seconds(60, lambda: (loop.quit() if loop.is_running() else None, False)[1])
                loop.run()
            finally:
                bus.signal_unsubscribe(subscription_id)

            if screenshot_path and os.path.exists(screenshot_path):
                self._images = [Image.open(screenshot_path)]
                self._offset_x = 0
                self._offset_y = 0

                if self._debug:
                    print(f"Portal screenshot loaded: {screenshot_path}")
                    self._images[0].save("/tmp/ocrScreenshot.png")

                # Clean up temporary file created by portal
                try:
                    os.remove(screenshot_path)
                except OSError:
                    pass

                return True
            else:
                if self._debug:
                    print("Portal screenshot: No result or file not found")
                return False

        except Exception as e:
            if self._debug:
                print(f"Portal screenshot error: {e}")
            return False

    def _capture_clipboard(self):
        """Capture image from clipboard."""
        try:
            if self._debug:
                print('get imagedata from clipboard')
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            pixbuf = clipboard.wait_for_image()
            self._images = [pixbuf_to_image(pixbuf)]
            if self._debug:
                if self._images[0] is None:
                    print('no image data in clipboard')
        except Exception as e:
            if self._debug:
                print(e)
            return False
        return self._images[0] is not None

    def _capture_file(self, file_path):
        """Capture image from file (image or PDF).

        Args:
            file_path: Path to image or PDF file

        Returns:
            bool: True if file was loaded successfully
        """
        if not file_path:
            return False
        if not os.path.exists(file_path):
            return False
        if not os.path.isfile(file_path):
            return False

        mime = MimeTypes()
        mime_type = mime.guess_type(file_path)

        if mime_type[0] != 'application/pdf':
            try:
                self._images = [Image.open(file_path)]
            except Exception:
                return False
        else:
            if not pdf2image_available:
                return False
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    images = convert_from_path(file_path, output_folder=temp_dir)
                    temp_images = []
                    for i, img in enumerate(images):
                        image_path = f'{temp_dir}/{i}.jpg'
                        img.save(image_path, 'JPEG')
                        temp_images.append(image_path)
                    self._images = list(map(Image.open, temp_images))
            except Exception:
                return False
        return True
