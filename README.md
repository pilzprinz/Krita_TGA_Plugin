# TGA Export Options — Krita Plugin

A Krita plugin that gives you full control over TGA export settings. It automatically shows an options dialog every time you save or export a `.tga` file.

![Krita](https://img.shields.io/badge/Krita-5.x-blue) ![Python](https://img.shields.io/badge/Python-3.6%2B-green) ![License](https://img.shields.io/badge/License-Free-brightgreen)

## The Story

I was creating a 4K texture mod for KOTOR 2, but the textures appeared upside down in the game. I discovered that the game uses a bottom-left origin, while Krita always exports with a top-left origin. I got tired of exporting to TGA, then opening the files in GIMP and exporting them again with “Bottom-left origin” checked. So I made this plugin to save artists a lot of time and effort. I think the Krita developers should add this export option to the main code by default.

## The Problem

Krita's built-in TGA export has limited options — you can't control the pixel origin, toggle RLE compression, change bit depth, or add a TGA 2.0 footer. This plugin fills those gaps.

## How It Works

1. Save or export your image as `.tga` using **File → Save As** or **File → Export**.
2. Krita writes the file to disk as usual.
3. The plugin detects the save (via `imageSaved` signal) and shows an options dialog.
4. Choose your settings and click **OK** — the plugin modifies the file on disk.
5. Click **Skip** to leave the file unchanged.

The plugin **does not** add any menu items — it works fully automatically, only for `.tga` files.

## Features

| Feature | Description |
|---------|-------------|
| **Origin** | Bottom-Left (TGA standard, max compatibility) or Top-Left (OpenGL, game engines) |
| **Bit Depth** | Keep as is, force 32-bit RGBA, or strip alpha to 24-bit RGB |
| **RLE Compression** | Toggle on/off — reduces file size for images with large flat-color areas |
| **TGA 2.0 Footer** | Adds `TRUEVISION-XFILE` signature for better compatibility with modern software |
| **Comment / Image ID** | Up to 255 ASCII characters embedded in the TGA header |
| **Persistent Settings** | All options are remembered between Krita sessions |

## Supported TGA Formats

- **Uncompressed:** Color-mapped (type 1), True-color (type 2), Grayscale (type 3)
- **RLE-compressed:** Color-mapped (type 9), True-color (type 10), Grayscale (type 11)
- **Pixel depths:** 8, 16, 24, 32 bpp
- **All origin positions:** Bottom-Left, Bottom-Right, Top-Left, Top-Right

<img width="413" height="546" alt="image" src="https://github.com/user-attachments/assets/eeb7e1ba-733d-4b0e-8c16-c05885ada399" />



## Installation

### Step 1: Find the pykrita folder

In Krita: **Settings → Manage Resources... → Open Resource Folder**

Inside, find or create a folder called `pykrita`.

| OS | Path |
|----|------|
| Linux | `~/.local/share/krita/pykrita/` |
| Windows | `%APPDATA%\krita\pykrita\` |
| macOS | `~/Library/Application Support/krita/pykrita/` |

### Step 2: Create the file structure

```
pykrita/
├── tga_export_options.desktop    ← file (next to the folder)
└── tga_export_options/           ← folder (all lowercase!)
    ├── __init__.py               ← plugin code
    └── Manual.html               ← manual (shown in Plugin Manager)
```

> ⚠️ **Important:** The folder must be named `tga_export_options` — **all lowercase**. Using `Tga_Export_Options` or any other case will cause "No module named" errors on Linux/macOS.

### Step 3: Copy the files

Download the files from the repository or copy their contents:

- **`tga_export_options.desktop`** — plugin metadata
- **`tga_export_options/__init__.py`** — plugin code
- **`tga_export_options/Manual.html`** — manual

### Step 4: Activate

1. Restart Krita
2. Go to **Settings → Configure Krita... → Python Plugin Manager**
3. Find **TGA Export Options** and check ✓ the box
4. Restart Krita once more
5. Done! The dialog will now appear automatically when saving `.tga` files.

## Troubleshooting

### The dialog doesn't appear

- Make sure the plugin is **enabled** in Python Plugin Manager.
- **Restart Krita twice** after enabling.
- Launch Krita from the command line to see debug messages.

### "No module named 'tga_export_options'"

- Check the folder name — it must be **all lowercase**: `tga_export_options`
- Make sure `__init__.py` is **inside** the folder, not next to it.
- Make sure `.desktop` is **next to** the folder, not inside it.

### "No plugins found in the archive"

If installing via zip import — make sure `.desktop` is in the root of the archive (not in a subfolder).

## Debug Output

Launch Krita from the command line to see plugin messages:

```
# On startup:
[TGA Export Options] __init__ called
[TGA Export Options] Settings loaded: origin=BL rle=False depth=0 footer=True
[TGA Export Options] setup() called
[TGA Export Options] imageSaved signal connected OK

# When saving a .tga file:
[TGA Export Options] imageSaved fired: '/path/to/myfile.tga'
[TGA Export Options] TGA detected, showing dialog...
[TGA Export Options] Origin set to Bottom-Left
[TGA Export Options] RLE applied
[TGA Export Options] TGA 2.0 footer added
[TGA Export Options] Done: TGA: origin=Bottom-Left, depth=keep, RLE, TGA2.0
```
