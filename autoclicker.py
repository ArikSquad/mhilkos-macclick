#!/usr/bin/env python3
"""
AutoClicker for macOS
----------------------
A lightweight autoclicker with a Tkinter GUI and a fully customizable,
re-bindable global hotkey (click "Change Hotkey", then press any key
combo -- it's captured live).

Requires: pynput  (pip3 install pynput)

macOS permissions required (System Settings > Privacy & Security):
  - Accessibility      (lets the app move/click the mouse)
  - Input Monitoring   (lets the app hear the global hotkey)
"""

import sys
import time
import threading

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    sys.exit("Tkinter is required but was not found in this Python install.")

try:
    from pynput import mouse, keyboard
    from pynput.keyboard import Key, KeyCode
except ImportError:
    # Show a friendly dialog even if launched with no Terminal attached
    # (e.g. double-clicked from Finder).
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing dependency",
        "This app requires the 'pynput' package.\n\n"
        "Open Terminal and run:\n\n    pip3 install pynput\n\n"
        "Then relaunch AutoClicker.",
    )
    sys.exit(1)


MODIFIERS = {Key.cmd, Key.ctrl, Key.alt, Key.shift}
MODIFIER_ORDER = [Key.cmd, Key.ctrl, Key.alt, Key.shift]

# Left/right variants all normalize to the generic modifier so it doesn't
# matter which physical key (or which side) the user presses.
_MODIFIER_ALIASES = {
    Key.shift_l: Key.shift, Key.shift_r: Key.shift,
    Key.ctrl_l: Key.ctrl, Key.ctrl_r: Key.ctrl,
    Key.alt_l: Key.alt, Key.alt_r: Key.alt,
    Key.cmd_l: Key.cmd, Key.cmd_r: Key.cmd,
}

_NAMES = {
    Key.cmd: "\u2318", Key.alt: "\u2325", Key.ctrl: "\u2303", Key.shift: "\u21e7",
    Key.space: "Space", Key.enter: "Return", Key.esc: "Esc", Key.tab: "Tab",
    Key.backspace: "\u232b", Key.delete: "Delete", Key.up: "\u2191",
    Key.down: "\u2193", Key.left: "\u2190", Key.right: "\u2192",
}
for _i in range(1, 21):
    _fkey = getattr(Key, f"f{_i}", None)
    if _fkey is not None:
        _NAMES[_fkey] = f"F{_i}"


def normalize_key(key):
    return _MODIFIER_ALIASES.get(key, key)


def key_display_name(key):
    if key in _NAMES:
        return _NAMES[key]
    if isinstance(key, KeyCode) and key.char:
        return key.char.upper()
    return str(key).replace("Key.", "").capitalize()


def combo_to_string(combo):
    if not combo:
        return "None set"
    mods = [k for k in MODIFIER_ORDER if k in combo]
    others = sorted((k for k in combo if k not in MODIFIER_ORDER), key=key_display_name)
    return "+".join(key_display_name(k) for k in mods + others)


class AutoClickerApp:
    DEFAULT_HOTKEY = frozenset({Key.f6})

    def __init__(self, root):
        self.root = root
        self.root.title("AutoClicker")
        self.root.resizable(False, False)

        self.mouse_controller = mouse.Controller()

        self.clicking = False
        self.click_thread = None

        self.pressed_keys = set()
        self.hotkey_combo = set(self.DEFAULT_HOTKEY)
        self.recording_hotkey = False
        self.picking_location = False

        self._build_gui()

        self.listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self.listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ GUI
    def _build_gui(self):
        outer = ttk.Frame(self.root, padding=16)
        outer.grid(row=0, column=0)

        row = 0

        # -- Interval -----------------------------------------------------
        ttk.Label(outer, text="Click Interval", font=("Helvetica", 13, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1

        self.hours = tk.StringVar(value="0")
        self.minutes = tk.StringVar(value="0")
        self.seconds = tk.StringVar(value="0")
        self.millis = tk.StringVar(value="100")

        interval_frame = ttk.Frame(outer)
        interval_frame.grid(row=row, column=0, columnspan=4, pady=(4, 0), sticky="w")
        for label, var in [
            ("Hours", self.hours), ("Minutes", self.minutes),
            ("Seconds", self.seconds), ("Milliseconds", self.millis),
        ]:
            col = ttk.Frame(interval_frame)
            col.pack(side="left", padx=(0, 14))
            ttk.Label(col, text=label).pack()
            ttk.Entry(col, textvariable=var, width=8, justify="center").pack()
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)
        row += 1

        # -- Click options --------------------------------------------------
        ttk.Label(outer, text="Click Options", font=("Helvetica", 13, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1

        self.button_var = tk.StringVar(value="Left")
        self.click_type_var = tk.StringVar(value="Single")

        opt_frame = ttk.Frame(outer)
        opt_frame.grid(row=row, column=0, columnspan=4, pady=(4, 0), sticky="w")
        ttk.Label(opt_frame, text="Mouse Button:").pack(side="left")
        ttk.OptionMenu(opt_frame, self.button_var, "Left", "Left", "Right", "Middle").pack(
            side="left", padx=(4, 20)
        )
        ttk.Label(opt_frame, text="Click Type:").pack(side="left")
        ttk.OptionMenu(opt_frame, self.click_type_var, "Single", "Single", "Double").pack(
            side="left", padx=(4, 0)
        )
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)
        row += 1

        # -- Location -------------------------------------------------------
        ttk.Label(outer, text="Click Location", font=("Helvetica", 13, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1

        self.location_mode = tk.StringVar(value="current")
        loc_frame = ttk.Frame(outer)
        loc_frame.grid(row=row, column=0, columnspan=4, pady=(4, 0), sticky="w")

        ttk.Radiobutton(
            loc_frame, text="Current mouse position", variable=self.location_mode, value="current"
        ).grid(row=0, column=0, columnspan=5, sticky="w")

        ttk.Radiobutton(
            loc_frame, text="Fixed position:", variable=self.location_mode, value="fixed"
        ).grid(row=1, column=0, sticky="w")
        self.pos_x = tk.StringVar(value="0")
        self.pos_y = tk.StringVar(value="0")
        ttk.Entry(loc_frame, textvariable=self.pos_x, width=6).grid(row=1, column=1, padx=(4, 2))
        ttk.Label(loc_frame, text="x").grid(row=1, column=2)
        ttk.Entry(loc_frame, textvariable=self.pos_y, width=6).grid(row=1, column=3, padx=(2, 8))
        ttk.Button(loc_frame, text="Pick (hover + Enter)", command=self._start_picking_location).grid(
            row=1, column=4
        )
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)
        row += 1

        # -- Repeat -----------------------------------------------------
        ttk.Label(outer, text="Repeat", font=("Helvetica", 13, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1

        self.repeat_mode = tk.StringVar(value="until_stopped")
        rep_frame = ttk.Frame(outer)
        rep_frame.grid(row=row, column=0, columnspan=4, pady=(4, 0), sticky="w")
        ttk.Radiobutton(
            rep_frame, text="Until stopped", variable=self.repeat_mode, value="until_stopped"
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            rep_frame, text="Fixed count:", variable=self.repeat_mode, value="count"
        ).grid(row=0, column=1, sticky="w", padx=(20, 4))
        self.repeat_count = tk.StringVar(value="10")
        ttk.Entry(rep_frame, textvariable=self.repeat_count, width=8).grid(row=0, column=2)
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)
        row += 1

        # -- Hotkey -----------------------------------------------------
        ttk.Label(outer, text="Hotkey", font=("Helvetica", 13, "bold")).grid(
            row=row, column=0, columnspan=4, sticky="w"
        )
        row += 1

        hk_frame = ttk.Frame(outer)
        hk_frame.grid(row=row, column=0, columnspan=4, pady=(4, 0), sticky="w")
        ttk.Label(hk_frame, text="Toggle start/stop:").pack(side="left", padx=(0, 8))
        self.hotkey_label_var = tk.StringVar(value=combo_to_string(self.hotkey_combo))
        self.hotkey_display = ttk.Label(
            hk_frame, textvariable=self.hotkey_label_var,
            font=("Menlo", 12, "bold"), foreground="#0066cc",
        )
        self.hotkey_display.pack(side="left", padx=(0, 10))
        self.record_button = ttk.Button(
            hk_frame, text="Change Hotkey", command=self._start_recording_hotkey
        )
        self.record_button.pack(side="left")
        row += 1

        self.hint_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.hint_var, foreground="#888888").grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(2, 0)
        )
        row += 1

        ttk.Separator(outer).grid(row=row, column=0, columnspan=4, sticky="ew", pady=12)
        row += 1

        # -- Status / Start-Stop -----------------------------------------
        status_frame = ttk.Frame(outer)
        status_frame.grid(row=row, column=0, columnspan=4, sticky="ew")
        self.status_var = tk.StringVar(value="Stopped")
        self.status_label = ttk.Label(
            status_frame, textvariable=self.status_var,
            font=("Helvetica", 14, "bold"), foreground="#cc0000",
        )
        self.status_label.pack(side="left")
        self.toggle_button = ttk.Button(status_frame, text="Start", command=self._toggle_clicking)
        self.toggle_button.pack(side="right")

    # -------------------------------------------------------- Hotkey logic
    def _start_recording_hotkey(self):
        self.recording_hotkey = True
        self.record_button.configure(text="Press keys... (Esc to cancel)", state="disabled")
        self.hotkey_label_var.set("...")
        self.hint_var.set("Press a key combination now.")

    def _finish_recording(self, combo):
        self.hotkey_combo = set(combo)
        self.recording_hotkey = False
        self.record_button.configure(text="Change Hotkey", state="normal")
        self.hotkey_label_var.set(combo_to_string(self.hotkey_combo))
        self.hint_var.set("Hotkey updated.")

    def _cancel_recording(self):
        self.recording_hotkey = False
        self.record_button.configure(text="Change Hotkey", state="normal")
        self.hotkey_label_var.set(combo_to_string(self.hotkey_combo))
        self.hint_var.set("Cancelled -- hotkey unchanged.")

    # ------------------------------------------------------------ Location
    def _start_picking_location(self):
        self.picking_location = True
        self.location_mode.set("fixed")
        self.hint_var.set("Hover the mouse where you want to click, then press Enter.")

    # --------------------------------------------------------- Key events
    def _on_key_press(self, key):
        normalized = normalize_key(key)
        self.pressed_keys.add(normalized)

        if self.picking_location and normalized == Key.enter:
            x, y = self.mouse_controller.position
            self.root.after(0, lambda: (self.pos_x.set(str(int(x))), self.pos_y.set(str(int(y)))))
            self.picking_location = False
            self.root.after(0, lambda: self.hint_var.set(f"Location set to ({int(x)}, {int(y)})."))
            return

        if self.recording_hotkey:
            if normalized == Key.esc:
                self.root.after(0, self._cancel_recording)
                return
            if normalized not in MODIFIERS:
                combo = frozenset(self.pressed_keys)
                self.root.after(0, lambda: self._finish_recording(combo))
            else:
                preview = combo_to_string(self.pressed_keys)
                self.root.after(0, lambda: self.hotkey_label_var.set(preview + "+..."))
            return

        # Normal mode: check for hotkey match on the "final" (non-modifier) key
        if normalized not in MODIFIERS:
            if frozenset(self.pressed_keys) == frozenset(self.hotkey_combo):
                self.root.after(0, self._toggle_clicking)

    def _on_key_release(self, key):
        normalized = normalize_key(key)
        self.pressed_keys.discard(normalized)

    # ------------------------------------------------------------ Clicking
    def _toggle_clicking(self):
        if self.clicking:
            self._stop_clicking()
        else:
            self._start_clicking()

    def _start_clicking(self):
        try:
            h = float(self.hours.get() or 0)
            m = float(self.minutes.get() or 0)
            s = float(self.seconds.get() or 0)
            ms = float(self.millis.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter valid numbers for the interval.")
            return

        interval = h * 3600 + m * 60 + s + ms / 1000.0
        if interval <= 0:
            messagebox.showerror("Invalid interval", "Interval must be greater than zero.")
            return

        fixed = self.location_mode.get() == "fixed"
        fx = fy = None
        if fixed:
            try:
                fx = int(float(self.pos_x.get()))
                fy = int(float(self.pos_y.get()))
            except ValueError:
                messagebox.showerror("Invalid position", "Fixed X/Y must be numbers.")
                return

        limit = None
        if self.repeat_mode.get() == "count":
            try:
                limit = int(self.repeat_count.get())
                if limit <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid count", "Repeat count must be a positive whole number.")
                return

        self.clicking = True
        self.status_var.set("Running")
        self.status_label.configure(foreground="#008800")
        self.toggle_button.configure(text="Stop")

        self.click_thread = threading.Thread(
            target=self._click_loop, args=(interval, fixed, fx, fy, limit), daemon=True
        )
        self.click_thread.start()

    def _stop_clicking(self):
        self.clicking = False
        self.status_var.set("Stopped")
        self.status_label.configure(foreground="#cc0000")
        self.toggle_button.configure(text="Start")

    def _click_loop(self, interval, fixed, fx, fy, limit):
        button_map = {
            "Left": mouse.Button.left, "Right": mouse.Button.right, "Middle": mouse.Button.middle,
        }
        button = button_map[self.button_var.get()]
        count = 2 if self.click_type_var.get() == "Double" else 1

        done = 0
        while self.clicking:
            if fixed and fx is not None:
                self.mouse_controller.position = (fx, fy)
            self.mouse_controller.click(button, count)
            done += 1
            if limit is not None and done >= limit:
                self.root.after(0, self._stop_clicking)
                break
            time.sleep(interval)

    # ---------------------------------------------------------------- Quit
    def _on_close(self):
        self.clicking = False
        try:
            self.listener.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
