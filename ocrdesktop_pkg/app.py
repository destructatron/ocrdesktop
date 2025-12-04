"""Main OCRdesktop application."""

import sys
import getopt
import time
import locale

from .constants import __version__
from .platform import ui_available, display_server, Gtk, Gdk
from .screenshot import ScreenshotCapture
from .ocr import OCRProcessor
from .color import ColorDetector
from .macro import MacroManager
from .gui import MainWindow


class OCRDesktopApp:
    """Main application class for OCRdesktop."""

    def __init__(self, debug=False):
        self._debug = debug
        self._show_help = False

        # Screenshot settings
        self._screenshot_mode = 0  # 0=window, 1=desktop, 2=clipboard, 3=file
        self._file_path = ''

        # Output settings
        self._send_to_clipboard = False
        self._print_to_stdout = False
        self._hide_gui = False

        # OCR settings
        self._language = 'eng'
        self._grayscale = False
        self._invert = False
        self._black_white = False
        self._black_white_value = 200
        self._scale_factor = 3

        # Color detection
        self._color_enabled = False
        self._color_max = 3

        # Components
        self._screenshot = ScreenshotCapture(debug=debug)
        self._ocr = OCRProcessor(language=self._language, scale_factor=self._scale_factor, debug=debug)
        self._color = ColorDetector(max_colors=self._color_max, debug=debug)
        self._macro = MacroManager(debug=debug)

        # Results
        self._ocr_text = ''
        self._word_list = []
        self._modified_images = []

        # Set locale for tesseract
        locale.setlocale(locale.LC_ALL, 'C')

    def run(self):
        """Run the application."""
        self._parse_command_line()

        if self._show_help:
            return

        # Handle macros for window/desktop mode
        if self._screenshot_mode in [0, 1]:
            if not self._hide_gui:
                self._macro.show_gui()
            else:
                if self._macro.macro_exists():
                    self._macro.run_macro()

        if self._debug:
            print("PreWaitForFinish")

        if self._screenshot_mode in [0, 1]:
            self._macro.wait_for_finish()
            time.sleep(0.5)

        # Take screenshot
        time.sleep(0.3)  # Brief delay before capture
        if self._screenshot.capture(self._screenshot_mode, self._file_path):
            self._run_ocr()

            if not self._hide_gui:
                self._show_gui()
            else:
                self._output_results()

    def _run_ocr(self):
        """Run OCR processing on captured images."""
        # Update OCR processor settings
        self._ocr.grayscale = self._grayscale
        self._ocr.invert = self._invert
        self._ocr.black_white = self._black_white
        self._ocr.black_white_value = self._black_white_value
        self._ocr.language = self._language

        # Update color detector
        self._color.enabled = self._color_enabled
        self._color.max_colors = self._color_max

        # Run OCR
        color_callback = self._color.get_color_string if self._color_enabled else None
        self._ocr_text, self._word_list, self._modified_images = self._ocr.process_images(
            self._screenshot.images,
            offset_x=self._screenshot.offset_x,
            offset_y=self._screenshot.offset_y,
            color_callback=color_callback,
            include_word_list=not self._hide_gui
        )

    def _output_results(self):
        """Output OCR results to clipboard/stdout."""
        if self._send_to_clipboard:
            self._set_text_to_clipboard(self._ocr_text)
        if self._print_to_stdout:
            print(self._ocr_text)

    def _set_text_to_clipboard(self, text):
        """Set text to system clipboard."""
        if not ui_available:
            if self._debug:
                print('GTK / GDK / GI is not available')
            return

        if self._debug:
            print("----_setTextToClipboard Start--")
            print(text)
            print("----_setTextToClipboard End----")
        try:
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
        except Exception:
            pass

    def _show_gui(self):
        """Show the main GUI window."""
        window = MainWindow(
            ocr_text=self._ocr_text,
            word_list=self._word_list,
            scale_factor=self._scale_factor,
            offset_x=self._screenshot.offset_x,
            offset_y=self._screenshot.offset_y,
            screenshot_mode=self._screenshot_mode,
            macro_manager=self._macro,
            debug=self._debug
        )
        window.set_refresh_callback(self._on_refresh)
        window.show_window()

    def _on_refresh(self, grayscale, invert, black_white):
        """Handle refresh/retry OCR from GUI."""
        self._grayscale = grayscale
        self._invert = invert
        self._black_white = black_white
        self._run_ocr()

    def _parse_command_line(self):
        """Parse command line arguments."""
        # Set hideGui if GTK is not available
        if not ui_available:
            if self._debug:
                print('GTK / GDK / GI is not available')
            self._hide_gui = True

        try:
            opts, args = getopt.getopt(sys.argv[1:], "hl:vndocCOx:gibt:m:f:")

            for opt, arg in opts:
                if opt == '-v':
                    self._debug = True
                    self._screenshot._debug = True
                    self._ocr._debug = True
                    self._color._debug = True
                    self._macro._debug = True
                    print('Debugmode ON')
                elif opt == '-f':
                    self._screenshot_mode = 3
                    self._file_path = arg
                elif opt == '-C':
                    if ui_available:
                        self._screenshot_mode = 2
                elif opt == '-d':
                    if ui_available:
                        self._screenshot_mode = 1
                elif opt == '-g':
                    self._grayscale = True
                elif opt == '-i':
                    self._invert = True
                elif opt == '-b':
                    self._grayscale = True
                    self._black_white = True
                elif opt == '-t':
                    self._black_white_value = int(arg)
                elif opt == '-c':
                    if ui_available:
                        self._send_to_clipboard = True
                elif opt == '-l':
                    self._language = arg
                elif opt == '-m':
                    if ui_available:
                        self._macro.load_macro_file(arg)
                elif opt == '-n':
                    self._hide_gui = True
                elif opt == '-o':
                    self._print_to_stdout = True
                elif opt == '-O':
                    self._color_enabled = True
                elif opt == '-x':
                    self._color_max = int(arg)
                elif opt == '-h':
                    self._print_help()
        except Exception:
            self._print_help()

    def _print_help(self):
        """Print help message."""
        print(f'Version {__version__}')
        print("ocrdesktop -h -l <lang> -n -d -c -C -o -O -x <Value> -v -i -g -b -t <Value> -f <File> -m <MacroFile>")
        print("-h               Print help with start")
        print("-l <lang>        set the OCR language default=eng")
        print("-n               hide GUI (use with -c,-o or -m")
        print("-d               OCR the Desktop")
        print("-c               Send to Clipboard")
        print("-f <File>        Read Image from File (PDF, JPG, PNG...)")
        print("-C               Read Image from Clipboard")
        print("-o               print to STDOUT")
        print("-O               analyze color information (will take more time)")
        print("-x <Value>       limit of colors to analyze (>1)")
        print("-v               print debug messages")
        print("-i               Invert the picture colors")
        print("-g               Grayscale picture")
        print("-b               break into hard black and white")
        print("-t <Value>       the value for breaking into black and white (-b) 0 (black) - 255 (white)")
        print("-m <MacroFile>   run a macro before starting.")
        self._show_help = True


def main():
    """Entry point for the application."""
    app = OCRDesktopApp()
    app.run()


if __name__ == "__main__":
    main()
