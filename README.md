# MacClik, an AutoClicker for macOS (Intel)

A small autoclicker with a GUI:
- Interval control (hours / minutes / seconds / milliseconds)
- Left / right / middle click, single or double
- Click at the current cursor position, or a fixed X/Y (with a "hover + Enter" picker)
- Click forever or a fixed number of times
- A **fully rebindable global hotkey** — click "Change Hotkey", then just press
  the key combo you want (e.g. `⌘+⇧+F6`). It's captured live, no typing key names.

Files in this folder:
| File | Purpose |
|---|---|
| `autoclicker.py` | The app itself |
| `requirements.txt` | Python dependency (`pynput`) |
| `AutoClicker.app` (+ `.zip`) | Ready-made double-clickable launcher (uses your system Python) |
| `setup.py` | Optional: build a fully standalone `.app` with `py2app` |

---

## 1. Quick start (recommended first)

Open **Terminal** and run:

```bash
cd path/to/this/folder
pip3 install -r requirements.txt
python3 autoclicker.py
```

The GUI window should appear immediately.

## 2. Grant macOS permissions (required — do this once)

Because the app moves the mouse and listens for a global hotkey, macOS needs
your explicit OK. Go to **System Settings → Privacy & Security**:

- **Accessibility** → enable **Terminal** (or `python3`) — lets it click/move the mouse
- **Input Monitoring** → enable **Terminal** (or `python3`) — lets it hear your hotkey

If you don't see it listed yet, run the app once, then it'll appear so you
can toggle it on. Restart the app after granting permission.

## 3. Using it

1. Set your interval, click type/button, location, and repeat mode.
2. Click **Start** (or press the hotkey shown, default `F6`).
3. Press the same hotkey again (or click **Stop**) to stop.
4. To change the hotkey: click **Change Hotkey**, then press any combination
   of keys (e.g. hold `Cmd+Shift` and tap `F7`). It locks in automatically.
   Press `Esc` while recording to cancel and keep the old one.

---

## Option A — Double-clickable launcher (`AutoClicker.app`)

`AutoClicker-app-bundle.zip` contains a ready `.app` that just runs
`autoclicker.py` with your system `python3` — no Terminal needed after the
one-time `pip3 install` above.

- Unzip it, then **right-click → Open** the first time (Gatekeeper will warn
  it's from an unidentified developer — this is expected for an unsigned app).
- If macOS says it's "damaged" or refuses to open, clear the quarantine flag:
  ```bash
  xattr -cr AutoClicker.app
  ```
  then right-click → Open again.
- Permission note: since this launcher just calls your system `python3`,
  the Accessibility/Input Monitoring grant will still show up as
  **python3**, not "AutoClicker" — that's normal for this lightweight
  approach.

## Option B — A "real" standalone app (`py2app`)

For a proper self-contained app (own icon slot, own entry in Privacy
settings, no dependency on system Python), build it **on your Intel Mac**:

```bash
pip3 install py2app pynput
python3 setup.py py2app
```

This produces `dist/AutoClicker.app`. Since you're building it on an Intel
Mac with Intel Python, the result is a native x86_64 app. Same Gatekeeper
notes as above apply (right-click → Open, or `xattr -cr` if needed), and
this time the permission prompts will be tied to "AutoClicker" itself.

---

## Notes

- Some games and apps prohibit automated clicking in their terms of
  service — worth a quick check if you plan to use this somewhere that matters.
- The hotkey match requires the exact combination held down (extra keys
  held at the same time will prevent a match) — this keeps it from
  triggering by accident.
