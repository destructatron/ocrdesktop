# ocrdesktop

Accessibility tool for using OCR to read inaccessible windows and dialogs.

> **Note:** This is a fork of the original [ocrdesktop by chrys87](https://github.com/chrys87/ocrdesktop), which appears to be unmaintained. This fork adds Wayland support and will continue to receive updates.

## Features

- OCR the active window or entire desktop
- Read images from clipboard or files (including PDFs)
- Interactive GUI with text and detailed table views
- Click-to-interact functionality (X11 only)
- Macro recording and playback (X11 only)
- Wayland support via XDG Desktop Portal

## Wayland Support

This fork adds Wayland support using the XDG Desktop Portal for screenshots. The application automatically detects whether you're running on X11 or Wayland and uses the appropriate method.

### How it works on Wayland
- Screenshots are captured via `org.freedesktop.portal.Screenshot`
- On first use, you may see a permission dialog to allow screenshots
- If your portal supports interactive selection (e.g., GNOME Shell), you can select specific windows or areas
- If interactive selection isn't available (e.g., using GNOME portal on non-GNOME compositors), it falls back to full-screen capture

### Wayland Limitations
- **Click interaction is not available** - pyatspi (AT-SPI) mouse/keyboard simulation is X11-only
- **Macro recording/playback is not available** - depends on pyatspi
- **Window-specific capture** depends on your portal implementation supporting interactive selection

## Dependencies

### Required
- python3
- tesseract
- tesseract-lang-<yourLanguageCode>
- python3-pillow
- python-pytesseract
- GTK3

### X11-only (automatically skipped on Wayland)
- python-atspi
- libwnck3

### Optional
- python-scipy (for color detection)
- python-webcolors (for color detection)
- python-pdf2image (for PDF support)

## Installation

### Arch Linux (dependencies only)
```bash
yay -S python tesseract tesseract-data-eng python-pillow python-atspi libwnck3 gtk3 python-webcolors python-scipy python-pytesseract python-pdf2image
```

### Manual Installation
Clone this repository and run directly:
```bash
git clone https://github.com/destructatron/ocrdesktop.git
cd ocrdesktop
./ocrdesktop
```

## Usage

```bash
# OCR the active window (default)
./ocrdesktop

# OCR the entire desktop
./ocrdesktop -d

# OCR from clipboard
./ocrdesktop -C

# OCR a file
./ocrdesktop -f image.png

# Run with debug output
./ocrdesktop -v

# See all options
./ocrdesktop -h
```

## Documentation

See the [Arch Wiki page](https://wiki.archlinux.org/index.php/Ocrdesktop) for more detailed documentation.

## Credits

- Original project by [chrys87](https://github.com/chrys87/ocrdesktop)
- Wayland support added by [destructatron](https://github.com/destructatron)



