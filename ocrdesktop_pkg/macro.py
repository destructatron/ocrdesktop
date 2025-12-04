"""Macro recording and playback functionality for OCRdesktop."""

import os
import shutil
import time
import _thread

from .constants import KEY_CODE, __version__, __appname__, __authors__, __website__, __copyright__, __license__, __comments__
from .platform import ui_available, display_server, Gtk, Gdk, pyatspi


class MacroManager:
    """Manages macro recording, saving, loading, and playback."""

    def __init__(self, debug=False):
        self._debug = debug
        self._macro_file = os.path.expanduser('~') + '/.activeOCRMacro.ocrm'
        self._macro_finished = False
        self._gui = None
        self._cancel_button = None
        self._run_button = None
        self._delete_button = None
        self._menubar = None
        self._accelerators = None
        self._grid = None
        self._label = None

    def macro_exists(self):
        """Check if a macro file exists."""
        return os.path.exists(self._macro_file) and os.path.isfile(self._macro_file)

    def load_macro_file(self, macro_path):
        """Load a macro from file.

        Args:
            macro_path: Path to macro file
        """
        if self._load_macro_exists(macro_path):
            if macro_path != self._macro_file:
                shutil.copy(macro_path, self._macro_file)

    def _load_macro_exists(self, path):
        """Check if a loadable macro file exists."""
        return os.path.exists(path) and os.path.isfile(path)

    def delete_macro(self):
        """Delete the active macro file."""
        if self.macro_exists():
            os.remove(self._macro_file)

    def run_macro(self):
        """Execute the loaded macro."""
        if not self.macro_exists():
            if self._debug:
                print("No Macro loaded..")
            return

        self._macro_finished = False
        with open(self._macro_file, "r") as f:
            for line in f:
                if self._debug:
                    print(f"_RunMacro: {line}")
                parts = line.strip().split(',')

                if parts[0] == 'c':
                    if parts[1] == 'delay':
                        time.sleep(float(parts[2]))
                elif parts[0] == 'k':
                    self._do_keyboard_step(int(parts[1]), parts[2], int(parts[3]))
                elif parts[0] == 'm':
                    self._do_mouse_step(int(parts[1]), int(parts[2]), parts[3])

        self._macro_finished = True

    def get_macro_finished(self):
        """Check if macro execution is finished."""
        return self._macro_finished

    def wait_for_finish(self):
        """Wait for macro execution to complete."""
        while not self.get_macro_finished() and self.macro_exists():
            time.sleep(0.3)
            if self._debug:
                print(self.get_macro_finished())
        time.sleep(0.2)
        self._macro_finished = False
        if self._debug:
            print("WaitForFinish complete")

    def write_keyboard_to_macro(self, key_value, key_string, event_type):
        """Write a keyboard event to macro file.

        Args:
            key_value: Key code value
            key_string: Key string representation
            event_type: Event type (press/release)
        """
        if pyatspi is None:
            return

        if event_type == pyatspi.KEY_PRESS:
            event_type_id = 0
        elif event_type == pyatspi.KEY_RELEASE:
            event_type_id = 1
        elif event_type == pyatspi.KEY_PRESSRELEASE:
            event_type_id = 2
        else:
            event_type_id = event_type

        with open(self._macro_file, "a") as f:
            f.write(f'k,{key_value},{key_string},{event_type_id}\n')

    def write_mouse_to_macro(self, x, y, mouse_event):
        """Write a mouse event to macro file.

        Args:
            x: X coordinate
            y: Y coordinate
            mouse_event: Mouse event type
        """
        with open(self._macro_file, "a") as f:
            f.write('c,delay,0.9\n')
            f.write(f'm,{x},{y},{mouse_event}\n')

    def _do_keyboard_step(self, key_value, key_string, event_type):
        """Execute a keyboard macro step.

        Args:
            key_value: Keycode or keysym
            key_string: Key string for composed input
            event_type: 0=press, 1=release, 2=pressrelease
        """
        if pyatspi is None:
            return

        if key_value == 0:
            if key_string:
                key_value = KEY_CODE.get(key_string, 0)
            else:
                if self._debug:
                    print(f"invalid keyboard macro: {key_value}, {key_string}")
                return

        if event_type == 0:
            pyatspi.Registry.generateKeyboardEvent(key_value, key_string, pyatspi.KEY_PRESS)
        elif event_type == 1:
            pyatspi.Registry.generateKeyboardEvent(key_value, key_string, pyatspi.KEY_RELEASE)
        elif event_type == 2:
            pyatspi.Registry.generateKeyboardEvent(key_value, key_string, pyatspi.KEY_PRESSRELEASE)

    def _do_mouse_step(self, x, y, mouse_event, pos_relation="abs"):
        """Execute a mouse macro step.

        Args:
            x: X coordinate
            y: Y coordinate
            mouse_event: Mouse event type
            pos_relation: Position relation (default: absolute)
        """
        if pyatspi is None:
            return

        pyatspi.Registry.generateMouseEvent(x, y, pos_relation)
        if mouse_event != 'None':
            pyatspi.Registry.generateMouseEvent(x, y, mouse_event)

    def thread_run_macro(self):
        """Run macro in a thread."""
        if self._debug:
            print("_threadRunMacro starts")
        self.run_macro()

    # GUI methods
    def show_gui(self):
        """Show the macro manager GUI."""
        if not self.macro_exists():
            return

        self._gui = self._create_gui()
        self._gui.show_all()
        ts = Gtk.get_current_event_time()
        self._gui.present_with_time(ts)
        self._run_button.grab_focus()
        Gtk.main()

    def _create_gui(self):
        """Create the macro manager GUI window."""
        dialog = Gtk.Window(title="Preclicks Manager")
        dialog.set_default_size(500, 60)
        dialog.set_modal(True)

        self._accelerators = Gtk.AccelGroup()
        self._menubar = Gtk.MenuBar()

        # Macro menu
        menu_macro = Gtk.Menu()
        item_save = Gtk.MenuItem(label="_Save As")
        item_save.set_use_underline(True)
        self._add_accelerator(item_save, "<Control>s", "activate")
        item_load = Gtk.MenuItem(label="_Load")
        item_load.set_use_underline(True)
        self._add_accelerator(item_load, "<Control>o", "activate")
        item_delete = Gtk.MenuItem(label="_Unload")
        item_delete.set_use_underline(True)
        self._add_accelerator(item_delete, "<Control>u", "activate")
        item_run = Gtk.MenuItem(label="_Run")
        item_run.set_use_underline(True)
        self._add_accelerator(item_run, "<Control>n", "activate")

        menu_macro.append(item_save)
        menu_macro.append(item_load)
        menu_macro.append(item_delete)
        menu_macro.append(item_run)

        item_save.connect("activate", self._on_save_macro, dialog)
        item_load.connect("activate", self._on_load_macro, dialog)
        item_delete.connect("activate", self._on_delete_macro, False)
        item_run.connect("activate", self._on_run_macro)

        # Help menu
        menu_help = Gtk.Menu()
        item_about = Gtk.MenuItem(label="_About")
        item_about.set_use_underline(True)
        menu_help.append(item_about)
        item_about.connect("activate", self._on_about_dialog, dialog)

        # Menu bar items
        item_macro_menu = Gtk.MenuItem(label="_Macro")
        item_macro_menu.set_use_underline(True)
        item_macro_menu.set_submenu(menu_macro)
        item_help_menu = Gtk.MenuItem(label="_Help")
        item_help_menu.set_use_underline(True)
        item_help_menu.set_submenu(menu_help)

        self._menubar.append(item_macro_menu)
        self._menubar.append(item_help_menu)

        dialog.add_accel_group(self._accelerators)

        # UI elements
        self._label = Gtk.Label(label="Preclicks are existing. What do you want do do with the preclicks?")
        self._label.set_selectable(True)

        self._run_button = Gtk.Button(label="_Run")
        self._run_button.set_use_underline(True)
        self._run_button.connect('clicked', self._on_run_macro)

        self._delete_button = Gtk.Button(label='_Unload')
        self._delete_button.set_use_underline(True)
        self._delete_button.connect('clicked', self._on_delete_macro)

        self._cancel_button = Gtk.Button(label='_Cancel')
        self._cancel_button.set_use_underline(True)
        self._cancel_button.connect('clicked', self._on_cancel)

        # Layout
        self._grid = Gtk.Grid()
        self._grid.attach(self._menubar, 0, 0, 3, 1)
        self._grid.attach(self._label, 0, 1, 3, 1)
        self._grid.attach(self._run_button, 0, 2, 1, 1)
        self._grid.attach(self._delete_button, 1, 2, 1, 1)
        self._grid.attach(self._cancel_button, 2, 2, 1, 1)

        dialog.connect("delete-event", self._on_cancel)
        dialog.connect('key-release-event', self._on_key_release)
        dialog.add(self._grid)

        return dialog

    def _add_accelerator(self, widget, accelerator, signal="activate"):
        """Add keyboard shortcut to widget."""
        if accelerator is not None:
            key, mod = Gtk.accelerator_parse(accelerator)
            widget.add_accelerator(signal, self._accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

    def _on_run_macro(self, widget):
        """Handle run macro button click."""
        self._gui.hide()
        _thread.start_new_thread(self.thread_run_macro, ())
        self._cancel(False)

    def _on_delete_macro(self, widget, close=True):
        """Handle delete macro button click."""
        self.delete_macro()
        if close:
            self._cancel(True)

    def _on_cancel(self, widget, event=None):
        """Handle cancel button click."""
        self._cancel(True)

    def _cancel(self, set_finished):
        """Close the GUI."""
        if self._gui is not None:
            self._gui.hide()
        if set_finished:
            self._macro_finished = True
        Gtk.main_quit()

    def _on_save_macro(self, widget, window):
        """Handle save macro menu item."""
        if not self.macro_exists():
            return

        dialog = Gtk.FileChooserDialog(
            "Save As", window, Gtk.FileChooserAction.SAVE,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.OK)
        )
        dialog.set_modal(True)
        dialog.set_default_size(800, 400)
        dialog.set_local_only(False)
        self._add_file_filters(dialog)
        Gtk.FileChooser.set_current_name(dialog, "NewOCRdesktopMakro.ocrm")

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            shutil.copy(self._macro_file, dialog.get_filename())
        dialog.destroy()

    def _on_load_macro(self, widget, window):
        """Handle load macro menu item."""
        dialog = Gtk.FileChooserDialog(
            "Please choose a file", window, Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK)
        )
        dialog.set_modal(True)
        dialog.set_default_size(800, 400)
        dialog.set_local_only(False)
        self._add_file_filters(dialog)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            shutil.copy(dialog.get_filename(), self._macro_file)
        dialog.destroy()

    def _add_file_filters(self, dialog):
        """Add file filters to file chooser dialog."""
        filter_text = Gtk.FileFilter()
        filter_text.set_name("Macro Textfiles")
        filter_text.add_mime_type("text/plain")
        filter_text.add_pattern("*.ocrm")
        dialog.add_filter(filter_text)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)

    def _on_about_dialog(self, widget, window):
        """Show about dialog."""
        dialog = Gtk.AboutDialog(window)
        dialog.set_authors(__authors__)
        dialog.set_website(__website__)
        dialog.set_copyright(__copyright__)
        dialog.set_license(__license__)
        dialog.set_version(__version__)
        dialog.set_program_name(__appname__)
        dialog.set_comments(__comments__)
        dialog.run()
        dialog.destroy()

    def _on_key_release(self, widget, event):
        """Handle key release events."""
        pass  # Reserved for future use
