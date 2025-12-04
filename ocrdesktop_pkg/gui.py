"""GUI components for OCRdesktop."""

import time
import _thread

from .constants import __version__, __appname__, __authors__, __website__, __copyright__, __license__, __comments__
from .platform import ui_available, display_server, Gtk, Gdk, GObject, pyatspi


class MainWindow(Gtk.Window):
    """Main OCRdesktop window for displaying OCR results."""

    def __init__(self, ocr_text='', word_list=None, scale_factor=3, offset_x=0, offset_y=0,
                 screenshot_mode=0, macro_manager=None, debug=False):
        self._debug = debug
        self._ocr_text = ocr_text
        self._word_list = word_list or []
        self._scale_factor = scale_factor
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._screenshot_mode = screenshot_mode
        self._macro = macro_manager
        self._display_server = display_server

        self._tree = None
        self._textbox = None
        self._textbuffer = None
        self._scrolled_window_tree = None
        self._scrolled_window_text = None
        self._keyboard_overlay_label = None
        self._keyboard_overlay_active = False
        self._grid = None
        self._menubar = None
        self._font_button = None
        self._accelerators = None
        self._view_mode = 0
        self._save_to_macro = False
        self._gtk_main_running = False

        # Image processing options (for retry)
        self._grayscale = False
        self._invert = False
        self._black_white = False

        # Callbacks for refresh
        self._on_refresh_callback = None

    def set_refresh_callback(self, callback):
        """Set callback for refresh/retry OCR."""
        self._on_refresh_callback = callback

    def set_ocr_results(self, ocr_text, word_list):
        """Update OCR results."""
        self._ocr_text = ocr_text
        self._word_list = word_list

    def show_window(self):
        """Create and show the main window."""
        self._create_window()
        self.set_modal(True)
        self.show_all()
        self._set_view(False)
        self._start_main()

    def _start_main(self):
        """Start GTK main loop."""
        self._gtk_main_running = True
        Gtk.main()

    def _cancel(self):
        """Close the window and quit GTK main loop."""
        if self._gtk_main_running:
            Gtk.main_quit()
            self._gtk_main_running = False

    def _create_window(self):
        """Create the main window with all components."""
        Gtk.Window.__init__(self, title="OCR")
        self.set_default_size(700, 800)

        self._grid = Gtk.Grid()
        self._accelerators = Gtk.AccelGroup()
        self._menubar = Gtk.MenuBar()

        # Create menus
        self._create_ocrdesktop_menu()
        if self._screenshot_mode in [0, 1]:  # Window or desktop mode
            self._create_interact_menu()
            self._create_macro_menu()
        self._create_help_menu()

        self.add_accel_group(self._accelerators)

        # Keyboard overlay label
        self._keyboard_overlay_label = Gtk.Label(label="Please insert keyboard commands. exit with: F4")
        self._keyboard_overlay_label.set_selectable(True)

        # Font button
        self._font_button = Gtk.FontButton()
        self._font_button.connect('font-set', self._on_font_set)

        # Create content views
        self._create_content_views()

        # Connect signals
        self.connect("delete-event", Gtk.main_quit)
        self.connect('key-release-event', self._on_key_release)

        # Layout
        self._grid.attach(self._menubar, 0, 0, 10, 1)
        self._grid.attach(self._keyboard_overlay_label, 0, 1, 10, 1)
        self._grid.attach(self._font_button, 0, 11, 3, 1)
        self.add(self._grid)

    def _create_content_views(self):
        """Create text and tree views for OCR results."""
        # Text view
        self._scrolled_window_text = Gtk.ScrolledWindow()
        self._textbox = Gtk.TextView()
        self._textbox.set_hexpand(True)
        self._textbox.set_vexpand(True)
        self._textbox.show()
        self._textbuffer = self._textbox.get_buffer()
        self._textbuffer.set_text(self._ocr_text)
        self._textbox.set_editable(False)
        if self._textbuffer.get_start_iter() is not None:
            self._textbuffer.place_cursor(self._textbuffer.get_start_iter())
        self._scrolled_window_text.add(self._textbox)

        # Tree view
        self._scrolled_window_tree = Gtk.ScrolledWindow()
        self._tree = Gtk.TreeView()
        self._tree.set_hexpand(True)
        self._tree.set_vexpand(True)
        self._tree.show()
        self._scrolled_window_tree.add(self._tree)

        # Set up tree model
        cols = [GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_INT,
                GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_INT,
                GObject.TYPE_INT, GObject.TYPE_INT]
        model = Gtk.ListStore(*cols)
        self._tree.set_model(model)

        # Hidden first column
        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("OCR Text", cell, text=0)
        column.set_visible(False)
        self._tree.append_column(column)

        # Visible columns
        headers = ['OCR Text', 'Fontsize', 'Color', 'Object', 'X Position', 'Y Position', 'Confidence']
        for i, header in enumerate(headers):
            cell = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(header, cell, text=i + 1)
            self._tree.append_column(column)

        # Populate tree
        model = self._tree.get_model()
        for row in self._word_list:
            row_iter = model.append(None)
            for i, cell in enumerate(row):
                col_index = i + 1
                if col_index == 5:  # X position
                    cell = cell / self._scale_factor + self._offset_x
                if col_index == 6:  # Y position
                    cell = cell / self._scale_factor + self._offset_y
                model.set_value(row_iter, col_index, cell)

        self._tree.set_search_column(1)
        self._grid.attach(self._scrolled_window_tree, 0, 1, 10, 10)
        self._grid.attach(self._scrolled_window_text, 0, 1, 10, 10)

    def _create_ocrdesktop_menu(self):
        """Create the OCRDesktop menu."""
        menu = Gtk.Menu()

        item_toggle_view = Gtk.MenuItem(label="Toggle V_iew")
        item_toggle_view.set_use_underline(True)
        self._add_accelerator(item_toggle_view, "<Alt>v", "activate")
        item_toggle_view.connect("activate", self._on_set_view, True)

        item_ocr_options = Gtk.MenuItem(label="_OCR Options")
        item_ocr_options.set_use_underline(True)
        option_submenu = Gtk.Menu()
        item_ocr_options.set_submenu(option_submenu)

        self._item_invert = Gtk.CheckMenuItem(label="_Invert")
        self._item_invert.set_use_underline(True)
        self._item_invert.set_active(self._invert)
        self._item_invert.connect("activate", self._toggle_invert)

        self._item_grayscale = Gtk.CheckMenuItem(label="_Grayscale")
        self._item_grayscale.set_use_underline(True)
        self._item_grayscale.set_active(self._grayscale)
        self._item_grayscale.connect("activate", self._toggle_grayscale)

        self._item_black_white = Gtk.CheckMenuItem(label="_Barrier Black White")
        self._item_black_white.set_use_underline(True)
        self._item_black_white.set_active(self._black_white)
        self._item_black_white.connect("activate", self._toggle_black_white)

        option_submenu.append(self._item_invert)
        option_submenu.append(self._item_grayscale)
        option_submenu.append(self._item_black_white)

        item_retry = Gtk.MenuItem(label="_Retry OCR")
        item_retry.set_use_underline(True)
        self._add_accelerator(item_retry, "F5", "activate")
        item_retry.connect("activate", self._on_refresh)

        item_clipboard = Gtk.MenuItem(label="Send to _Clipboard")
        item_clipboard.set_use_underline(True)
        self._add_accelerator(item_clipboard, "<Control>b", "activate")
        item_clipboard.connect("activate", self._on_send_to_clipboard)

        item_close = Gtk.MenuItem(label="_Close")
        item_close.set_use_underline(True)
        self._add_accelerator(item_close, "<Control>q", "activate")
        item_close.connect("activate", Gtk.main_quit)

        menu.append(item_toggle_view)
        menu.append(item_ocr_options)
        menu.append(item_retry)
        menu.append(item_clipboard)
        menu.append(item_close)

        item_ocrdesktop = Gtk.MenuItem(label="_OCRDesktop")
        item_ocrdesktop.set_use_underline(True)
        item_ocrdesktop.set_submenu(menu)
        self._menubar.append(item_ocrdesktop)

    def _create_interact_menu(self):
        """Create the Interact menu (X11 only features)."""
        menu = Gtk.Menu()

        item_preclick = Gtk.CheckMenuItem(label="_Preclick")
        item_preclick.set_use_underline(True)
        self._add_accelerator(item_preclick, "<Control>p", "activate")
        item_preclick.connect("activate", self._set_save_to_macro)

        item_left = Gtk.MenuItem(label="_Left Click")
        item_left.set_use_underline(True)
        self._add_accelerator(item_left, "<Control>l", "activate")
        item_left.connect("activate", self._on_left_click)

        item_double = Gtk.MenuItem(label="_Double Click")
        item_double.set_use_underline(True)
        self._add_accelerator(item_double, "<Control>d", "activate")
        item_double.connect("activate", self._on_double_click)

        item_right = Gtk.MenuItem(label="_Right Click")
        item_right.set_use_underline(True)
        self._add_accelerator(item_right, "<Control>r", "activate")
        item_right.connect("activate", self._on_right_click)

        item_middle = Gtk.MenuItem(label="_Middle Click")
        item_middle.set_use_underline(True)
        self._add_accelerator(item_middle, "<Control>m", "activate")
        item_middle.connect("activate", self._on_middle_click)

        item_route = Gtk.MenuItem(label="Route _To")
        item_route.set_use_underline(True)
        self._add_accelerator(item_route, "<Control>t", "activate")
        item_route.connect("activate", self._route_to_point)

        item_sendkey = Gtk.MenuItem(label="Send _Key")
        item_sendkey.set_use_underline(True)
        self._add_accelerator(item_sendkey, "<Control>k", "activate")
        item_sendkey.connect("activate", self._send_key_mode)

        menu.append(item_preclick)
        menu.append(item_left)
        menu.append(item_double)
        menu.append(item_right)
        menu.append(item_middle)
        menu.append(item_route)
        menu.append(item_sendkey)

        item_interact = Gtk.MenuItem(label="_Interact")
        item_interact.set_use_underline(True)
        item_interact.set_submenu(menu)
        self._menubar.append(item_interact)

    def _create_macro_menu(self):
        """Create the Macro menu."""
        menu = Gtk.Menu()

        item_save = Gtk.MenuItem(label="_Save As")
        item_save.set_use_underline(True)
        self._add_accelerator(item_save, "<Control>s", "activate")
        item_save.connect("activate", self._macro._on_save_macro if self._macro else lambda w: None, self)

        item_load = Gtk.MenuItem(label="_Load")
        item_load.set_use_underline(True)
        self._add_accelerator(item_load, "<Control>o", "activate")
        item_load.connect("activate", self._macro._on_load_macro if self._macro else lambda w: None, self)

        item_delete = Gtk.MenuItem(label="_Unload")
        item_delete.set_use_underline(True)
        self._add_accelerator(item_delete, "<Control>u", "activate")
        item_delete.connect("activate", self._macro._on_delete_macro if self._macro else lambda w: None, False)

        item_run = Gtk.MenuItem(label="_Run")
        item_run.set_use_underline(True)
        self._add_accelerator(item_run, "<Control>n", "activate")
        item_run.connect("activate", self._on_run_macro)

        menu.append(item_save)
        menu.append(item_load)
        menu.append(item_delete)
        menu.append(item_run)

        item_macro = Gtk.MenuItem(label="_Macro")
        item_macro.set_use_underline(True)
        item_macro.set_submenu(menu)
        self._menubar.append(item_macro)

    def _create_help_menu(self):
        """Create the Help menu."""
        menu = Gtk.Menu()

        item_about = Gtk.MenuItem(label="_About")
        item_about.set_use_underline(True)
        item_about.connect("activate", self._on_about_dialog, self)

        menu.append(item_about)

        item_help = Gtk.MenuItem(label="_Help")
        item_help.set_use_underline(True)
        item_help.set_submenu(menu)
        self._menubar.append(item_help)

    def _add_accelerator(self, widget, accelerator, signal="activate"):
        """Add keyboard shortcut to widget."""
        if accelerator is not None:
            key, mod = Gtk.accelerator_parse(accelerator)
            widget.add_accelerator(signal, self._accelerators, key, mod, Gtk.AccelFlags.VISIBLE)

    def _on_font_set(self, widget):
        """Handle font selection."""
        font_desc = widget.get_font_desc()
        self._textbox.modify_font(label="font_description")

    def _on_set_view(self, widget, toggle=True):
        """Handle view toggle."""
        self._set_view(toggle)

    def _set_view(self, toggle):
        """Set the current view (text or tree)."""
        self._scrolled_window_tree.hide()
        self._scrolled_window_text.hide()
        self._keyboard_overlay_label.hide()

        if self._keyboard_overlay_active:
            self._keyboard_overlay_label.show()
            return

        self._set_focus()

        if toggle:
            self._view_mode = 1 if self._view_mode == 0 else 0

        if self._view_mode == 1:
            self._scrolled_window_tree.show()
            self._tree.grab_focus()
        else:
            self._scrolled_window_text.show()
            self._textbox.grab_focus()

    def _set_focus(self):
        """Sync focus between views."""
        if self._view_mode == 0 and self._textbuffer:
            position = self._textbuffer.get_iter_at_offset(self._textbuffer.props.cursor_position)
            if self._textbuffer.get_start_iter() is not None:
                text = self._textbuffer.get_text(self._textbuffer.get_start_iter(), position, True)
                self._tree.set_cursor(text.count('\n') + text.count(' '))

    def _toggle_grayscale(self, widget):
        """Toggle grayscale option."""
        self._grayscale = widget.get_active()
        if not self._grayscale:
            self._item_black_white.set_active(False)

    def _toggle_invert(self, widget):
        """Toggle invert option."""
        self._invert = widget.get_active()

    def _toggle_black_white(self, widget):
        """Toggle black/white option."""
        self._black_white = widget.get_active()
        if self._black_white:
            self._item_grayscale.set_active(True)

    def _on_refresh(self, widget):
        """Handle refresh/retry OCR."""
        if self._on_refresh_callback:
            self._on_refresh_callback(self._grayscale, self._invert, self._black_white)

    def _on_send_to_clipboard(self, widget):
        """Send OCR text to clipboard."""
        self._set_text_to_clipboard(self._ocr_text)

    def _set_text_to_clipboard(self, text):
        """Set text to system clipboard."""
        if not ui_available:
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

    def _set_save_to_macro(self, widget):
        """Toggle macro recording."""
        self._save_to_macro = widget.get_active()

    def _get_selected_entry(self):
        """Get selected entry coordinates from tree view."""
        if not self._tree:
            return None

        selection = self._tree.get_selection()
        if not selection:
            return None

        model, paths = selection.get_selected_rows()
        if not paths:
            return None

        return (model.get_value(model.get_iter(paths[0]), 5),
                model.get_value(model.get_iter(paths[0]), 6))

    # Click handlers (X11 only)
    def _on_left_click(self, widget):
        """Handle left click action."""
        self._set_focus()
        coords = self._get_selected_entry()
        if coords:
            self.hide()
            _thread.start_new_thread(self._thread_do_click, (coords[0], coords[1], "b1c"))

    def _on_double_click(self, widget):
        """Handle double click action."""
        self._set_focus()
        coords = self._get_selected_entry()
        if coords:
            self.hide()
            _thread.start_new_thread(self._thread_do_click, (coords[0], coords[1], "b1d"))

    def _on_right_click(self, widget):
        """Handle right click action."""
        self._set_focus()
        coords = self._get_selected_entry()
        if coords:
            self.hide()
            _thread.start_new_thread(self._thread_do_click, (coords[0], coords[1], "b3c"))

    def _on_middle_click(self, widget):
        """Handle middle click action."""
        self._set_focus()
        coords = self._get_selected_entry()
        if coords:
            self.hide()
            _thread.start_new_thread(self._thread_do_click, (coords[0], coords[1], "b2c"))

    def _route_to_point(self, widget):
        """Route mouse to selected point."""
        self._set_focus()
        self.hide()
        coords = self._get_selected_entry()
        if coords:
            _thread.start_new_thread(self._thread_route_to, (coords[0], coords[1]))

    def _thread_do_click(self, x, y, mouse_event, delay=0.8):
        """Perform click in thread."""
        if pyatspi is None:
            self._cancel()
            return

        if self._save_to_macro and self._macro:
            self._macro.write_mouse_to_macro(x, y, mouse_event)
        else:
            time.sleep(delay)
            pyatspi.Registry.generateMouseEvent(x, y, mouse_event)
        self._cancel()

    def _thread_route_to(self, x, y, delay=0.8):
        """Route mouse to point in thread."""
        if pyatspi is None:
            self._cancel()
            return

        if self._save_to_macro and self._macro:
            self._macro.write_mouse_to_macro(x, y, 'None')
        else:
            time.sleep(delay)
            pyatspi.Registry.generateMouseEvent(x, y, "abs")
        self._cancel()

    def _send_key_mode(self, widget):
        """Enter send key mode."""
        if pyatspi is None:
            return

        self._keyboard_overlay_active = True
        if self._debug:
            print("sendKeyMode")

        pyatspi.Registry.registerKeystrokeListener(
            self._on_send_key,
            mask=pyatspi.allModifiers(),
            kind=(pyatspi.KEY_PRESS, pyatspi.KEY_RELEASE, pyatspi.KEY_PRESSRELEASE),
            synchronous=True,
            preemptive=True
        )
        self._set_view(False)
        if self._debug:
            print("Keyboardlistener is registered")

    def _on_send_key(self, event):
        """Handle keyboard events in send key mode."""
        if pyatspi is None:
            return True

        if self._debug:
            print("_onSendKey")
            print(f'Type: {event.type}')
            print(f'String: {event.event_string}')
            print(f'ID: {event.id}')
            print(f'hw_code: {event.hw_code}')

        if event.type == pyatspi.Atspi.EventType.KEY_PRESSED_EVENT:
            if event.event_string == 'F4':
                self._keyboard_overlay_active = False
                self._set_view(False)
                pyatspi.Registry.deregisterKeystrokeListener(self._on_send_key)
                if self._debug:
                    print('deregisterKeystrokeListener')
                return True
            event_type_id = 0
        elif event.type == pyatspi.Atspi.EventType.KEY_RELEASED_EVENT:
            event_type_id = 1
        else:
            event_type_id = 2

        if self._macro:
            self._macro.write_keyboard_to_macro(0, event.event_string, event_type_id)
        return True

    def _on_run_macro(self, widget):
        """Run loaded macro."""
        if self._macro and self._macro.macro_exists():
            self.hide()
            _thread.start_new_thread(self._thread_run_macro, ())
        else:
            dialog = Gtk.MessageDialog(
                self, 0, Gtk.MessageType.INFO,
                Gtk.ButtonsType.OK, "No Macro loaded"
            )
            dialog.format_secondary_text("You have to load a macro for execution.")
            dialog.run()
            dialog.destroy()

    def _thread_run_macro(self):
        """Run macro in thread."""
        if self._macro:
            self._macro.thread_run_macro()
        self._cancel()

    def _on_key_release(self, widget, event):
        """Handle key release events."""
        pass  # Reserved for future use

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
