# Steam Download Symlink Helper (GUI)

A small Tkinter GUI to help move Steam's `steamapps/downloading` (and optionally `steamapps/temp`) to a faster SSD and replace them with symlinks. This can speed up downloads while keeping the main Steam library on a larger HDD.

## What it does
- Detects Steam libraries on Linux (native and Flatpak) and lists their `steamapps` folders
- Lets you pick an SSD destination folder
- For each selected library, creates a stable target folder on the SSD and:
  - Moves contents of `steamapps/downloading` (and optionally `steamapps/temp`) if they exist and are non-empty
  - Replaces them with symlinks pointing to the SSD
  - Creates missing folders as needed
  - Skips or asks before replacing existing symlinks

## Requirements
- Python 3 with Tkinter installed
- Linux with Steam installed (native or Flatpak)

## Run it
In this repo directory:

```fish
python3 steam_symlink_gui.py
```

Notes for fish shell:
- No special flags needed. If Tkinter is missing, install the `tk` package for your distro.

## Typical paths
- Native Steam: `~/.local/share/Steam/steamapps`
- Legacy symlink: `~/.steam/steam/steamapps`
- Flatpak Steam: `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps`

## Revert
To undo, remove the symlink(s) in the library `steamapps` and recreate directories if desired. Optionally move the contents back from the SSD target.

## Caution
- Ensure there’s enough space on the SSD for temporary download data.
- Close Steam before making changes for safety.
- This tool alters only `downloading` and optionally `temp` within chosen `steamapps`.

## Windows usage
This tool can also run on Windows, but symlink creation has a few requirements.

### Prerequisites
- Windows 10/11
- Python 3 with Tkinter (typically included in Windows Python installers)
- One of the following to allow creating symlinks:
  - Developer Mode enabled (Settings > Privacy & Security > For developers > Developer Mode)
  - OR run the script “as Administrator” when creating links

### Typical Steam paths on Windows
- Default: `C:\Program Files (x86)\Steam\steamapps`
- Additional libraries: configured under Steam > Settings > Storage (browse to the library and locate `steamapps`)

### Run
- Close Steam.
- Run the script normally:

```powershell
py -3 .\steam_symlink_gui.py
```

- Pick your Steam `steamapps` folder and choose your fast SSD destination.
- Click Create Symlinks.

If you see a permissions error creating the symlink:
- Either enable Developer Mode and retry, or
- Re-run your terminal as Administrator and run the script again.

### Manual fallback (mklink)
If you prefer manual steps, here’s how you would link `downloading` yourself (run from an elevated PowerShell):

```powershell
# Example paths - adjust to your actual library and SSD target
$steamapps = "C:\\Program Files (x86)\\Steam\\steamapps"
$target    = "D:\\SteamLibrary\\downloading"

# Create the target directory if missing
New-Item -ItemType Directory -Force -Path $target | Out-Null

# Move contents if a folder already exists
if (Test-Path "$steamapps\\downloading" -PathType Container) {
  robocopy "$steamapps\\downloading" "$target" /E /MOVE | Out-Null
  Remove-Item "$steamapps\\downloading" -Recurse -Force
}

# Create directory symlink
cmd /c mklink /D "$steamapps\\downloading" "$target"
```

Notes:
- You can repeat the same for `temp` if you want to link it as well.
- On Windows, directory symlinks require Developer Mode or admin rights.
