# Close App After Copy - Feature Plan

## Problem

When taking a screenshot and copying it (Ctrl+C), the user wants the app to close automatically. Currently, they have to manually close the window after each screenshot.

There's already an `exit-method` setting with "Copy and Close" — but that only fires when you click the X button or press Alt+F4, NOT when you press Ctrl+C. So this doesn't solve the actual problem.

## Solution

Add a `close-after-copy` boolean GSettings key. When enabled, pressing Ctrl+C copies the image to clipboard AND closes the window immediately.

---

## Files to Modify

### 1. GSettings Schema
**File:** `data/be.alexandervanhee.gradia.gschema.xml`
- Add new boolean key `close-after-copy` (default: `false`)
- Place it near the other "exiting" keys

### 2. Settings Backend
**File:** `gradia/backend/settings.py`
- Add `close_after_copy` property (getter + setter)
- Read/write from `close-after-copy` GSettings key

### 3. Window / Copy Action
**File:** `gradia/ui/window.py`
- Modify the copy action (`<Primary>c`) to check the setting
- If `close_after_copy` is enabled, copy to clipboard AND close the window
- Need to hook into the copy flow — currently the copy action just calls `export_manager.copy_to_clipboard()`, which is async. The close needs to happen after the copy completes.

### 4. Preferences UI (Blueprint)
**File:** `data/ui/preferences_window.blp`
- Add a new `Adw.SwitchRow` under the "Closing" group, next to the existing exiting combo
- Label: "Close app after copy" / subtitle: "Automatically close after pressing Ctrl+C"

### 5. Preferences Window (Python)
**File:** `gradia/ui/preferences/preferences_window.py`
- Add `close_after_copy_switch` as a template child
- Bind it to the `close-after-copy` GSettings key
- Import new switch in the class definition

---

## How to Run Locally (Outside Flatpak)

The app is built with **Meson** and depends on:
- GTK4 (`gtk4 >= 4.12.0`)
- libadwaita (`libadwaita-1 >= 1.5.0`)
- Python 3 + PyGObject (`pygobject-3.0 >= 3.48.0`)
- gtksourceview-5

### Steps

1. Install system dependencies:
   ```bash
   sudo apt install meson ninja-build \
     libgtk-4-dev libadwaita-1-dev \
     libgtksourceview-5-dev \
     python3-dev python3-gi python3-gi-cairo \
     gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtksource-5 \
     libglib2.0-dev python3-pil
   ```

2. Install Python dependencies:
   ```bash
   pip install pycairo Pillow
   ```

3. Configure with meson:
   ```bash
   meson setup build --prefix=/usr/local
   ```

4. Build:
   ```bash
   meson compile -C build
   ```

5. Run (from build dir):
   ```bash
   meson devenv -C build gradia/main.py
   ```
   Or install and run:
   ```bash
   sudo meson install -C build
   gradia
   ```

### Preserving Settings

GSettings keys are stored at `~/.config/glib-2.0/gsettings/*.xml` or in the dconf database. If the installed Flatpak and local build use the **same `application-id`** (`be.alexandervanhee.gradia`), they'll share the same GSettings backend — but the Flatpak likely uses a sandboxed dconf, so **settings won't carry over automatically**.

**To preserve settings:**
1. Export the Flatpak's dconf database:
   ```bash
   flatpak run --command=dconf be.alexandervanhee.gradia dconf dump /be/alexandervanhee/gradia/
   ```
2. Import it into your local dconf:
   ```bash
   dconf load /be/alexandervanhee/gradia/ < flatpak_settings.txt
   ```

Alternatively, if the local build installs with the same app ID, the schemas will merge into the system dconf database and settings will be shared.

### Important: Schema Collision

If you install locally with `--prefix=/usr/local`, the schema goes to `/usr/local/share/glib-2.0/schemas/`. The Flatpak ships its own schema inside the app bundle. They should coexist — the installed one takes priority over the Flatpak's bundled one. As long as the schema ID matches (`be.alexandervanhee.gradia`), settings will merge correctly.

---

## Implementation Order

1. ~~Research & plan~~ (this file)
2. Add GSettings key (`gschema.xml`)
3. Add settings property (`settings.py`)
4. Wire up copy action to close (`window.py`)
5. Add toggle to preferences UI (`preferences_window.blp` + `preferences_window.py`)
6. Build & test locally
