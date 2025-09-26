#!/usr/bin/env python3
import os
import sys
import shutil
import re
import platform
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception as e:
    print("Tkinter is required to run this GUI:", e, file=sys.stderr)
    sys.exit(1)


APP_TITLE = "Steam Download Symlink Helper"


def _expanduser(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def find_libraryfolders_files() -> list[Path]:
    """Return plausible paths to libraryfolders.vdf files on Linux, including Flatpak."""
    candidates = [
        _expanduser("~/.local/share/Steam/steamapps/libraryfolders.vdf"),
        _expanduser("~/.steam/steam/steamapps/libraryfolders.vdf"),
        _expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/libraryfolders.vdf"),
    ]
    seen = []
    for p in candidates:
        if p.exists() and p.is_file():
            seen.append(p)
    return seen


def parse_libraryfolders(vdf_path: Path) -> list[Path]:
    """Parse a libraryfolders.vdf and return steam library root paths (SteamLibrary dirs).

    We use a simple regex to extract all values of "path" entries. This works for both
    old and new VDF formats well enough for our purpose.
    """
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    paths = re.findall(r'"path"\s+"([^"]+)"', text)
    results: list[Path] = []
    for p in paths:
        lib = _expanduser(p)
        if lib.exists():
            results.append(lib)
    return results


def discover_steamapps_dirs() -> list[Path]:
    """Return a list of existing steamapps directories across all libraries."""
    steamapps = set()

    # Defaults
    default_steamapps = [
        _expanduser("~/.local/share/Steam/steamapps"),
        _expanduser("~/.steam/steam/steamapps"),
        _expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps"),
    ]
    for p in default_steamapps:
        if p.exists() and p.is_dir():
            steamapps.add(p)

    # From libraryfolders files
    for vdf in find_libraryfolders_files():
        for lib_root in parse_libraryfolders(vdf):
            sa = lib_root / "steamapps"
            if sa.exists() and sa.is_dir():
                steamapps.add(sa)

    # Sort nicely
    return sorted(steamapps, key=lambda p: str(p))


def is_symlink_to(path: Path, target: Path) -> bool:
    try:
        return path.is_symlink() and path.resolve() == target.resolve()
    except Exception:
        return False


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def dir_is_empty(path: Path) -> bool:
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    try:
        return next(path.iterdir(), None) is None
    except Exception:
        return False


def create_symlink_safe(link_path: Path, target_path: Path) -> tuple[bool, str]:
    """
    Safely create a symbolic link with proper Windows error handling.
    Returns (success, message).
    """
    try:
        # On Windows, we need directory symlinks for directories
        if platform.system() == "Windows":
            os.symlink(str(target_path), str(link_path), target_is_directory=True)
        else:
            os.symlink(str(target_path), str(link_path))
        return True, f"Successfully created symlink: {link_path} -> {target_path}"
    except OSError as e:
        if platform.system() == "Windows" and e.winerror == 1314:
            # Privilege error on Windows
            return False, (
                f"Failed to create symlink due to insufficient privileges.\n"
                f"To fix this, either:\n"
                f"1. Run this application as Administrator, OR\n"
                f"2. Enable Developer Mode in Windows Settings:\n"
                f"   Settings > Update & Security > For developers > Developer Mode\n\n"
                f"Target: {link_path} -> {target_path}"
            )
        else:
            return False, f"Failed to create symlink: {e}\nTarget: {link_path} -> {target_path}"
    except Exception as e:
        return False, f"Unexpected error creating symlink: {e}\nTarget: {link_path} -> {target_path}"


def move_dir_contents(src: Path, dst: Path):
    ensure_dir(dst)
    for item in src.iterdir():
        shutil.move(str(item), str(dst / item.name))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(720, 420)

        self._make_widgets()
        self._populate_defaults()
        self._show_windows_warning()

    def _make_widgets(self):
        pad = 8
        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=pad, pady=pad)

        # Steam library (steamapps)
        row = 0
        ttk.Label(main, text="Steam library (steamapps) to modify:").grid(row=row, column=0, sticky="w")
        self.steamapps_var = tk.StringVar()
        self.steamapps_combo = ttk.Combobox(main, textvariable=self.steamapps_var, width=80, state="readonly")
        self.steamapps_combo.grid(row=row+1, column=0, sticky="we", columnspan=2, pady=(0, pad))
        ttk.Button(main, text="Browse…", command=self._browse_steamapps).grid(row=row+1, column=2, padx=(pad, 0))

        # Destination base on SSD
        row += 2
        ttk.Label(main, text="Destination base folder on SSD:").grid(row=row, column=0, sticky="w")
        self.dest_var = tk.StringVar()
        self.dest_entry = ttk.Entry(main, textvariable=self.dest_var, width=80)
        self.dest_entry.grid(row=row+1, column=0, sticky="we", columnspan=2, pady=(0, pad))
        ttk.Button(main, text="Browse…", command=self._browse_dest).grid(row=row+1, column=2, padx=(pad, 0))

        # Options
        row += 2
        self.link_temp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main, text="Also link steamapps/temp", variable=self.link_temp_var).grid(row=row, column=0, sticky="w")

        # Action buttons
        row += 1
        btns = ttk.Frame(main)
        btns.grid(row=row, column=0, columnspan=3, sticky="we", pady=(pad, pad))
        ttk.Button(btns, text="Create Symlinks", command=self._run).pack(side=tk.LEFT)
        ttk.Button(btns, text="Quit", command=self.destroy).pack(side=tk.LEFT, padx=(pad, 0))

        # Log area
        row += 1
        ttk.Label(main, text="Log:").grid(row=row, column=0, sticky="w")
        row += 1
        self.log = tk.Text(main, height=12)
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew")

        main.columnconfigure(0, weight=1)
        main.rowconfigure(row, weight=1)

    def _populate_defaults(self):
        options = discover_steamapps_dirs()
        opts = [str(p) for p in options]
        self.steamapps_combo["values"] = opts
        if opts:
            self.steamapps_combo.current(0)

        # Suggest an SSD-like default if present
        for hint in ("/mnt", "/media", "/run/media"):
            p = Path(hint)
            if p.exists():
                self.dest_var.set(str(p))
                break

    def _browse_steamapps(self):
        d = filedialog.askdirectory(title="Select steamapps directory")
        if d:
            self.steamapps_var.set(d)

    def _browse_dest(self):
        d = filedialog.askdirectory(title="Select destination base on SSD")
        if d:
            self.dest_var.set(d)

    def _append_log(self, msg: str):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    def _confirm(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def _show_windows_warning(self):
        """Show Windows-specific symlink privilege warning if on Windows."""
        if platform.system() == "Windows":
            warning_msg = (
                "Windows Symlink Requirements:\n\n"
                "This application creates symbolic links, which on Windows requires either:\n"
                "• Running as Administrator, OR\n"
                "• Having Developer Mode enabled\n\n"
                "To enable Developer Mode:\n"
                "Settings > Update & Security > For developers > Developer Mode\n\n"
                "If you encounter privilege errors, please enable Developer Mode or run as Administrator."
            )
            messagebox.showinfo("Windows Setup Information", warning_msg)

    def _run(self):
        try:
            self._do_run()
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {e}")
            self._append_log(f"ERROR: {e}")

    def _do_run(self):
        sa_str = self.steamapps_var.get().strip()
        dest_base_str = self.dest_var.get().strip()

        if not sa_str:
            messagebox.showwarning("Missing input", "Please select a steamapps directory to modify.")
            return
        if not dest_base_str:
            messagebox.showwarning("Missing input", "Please select a destination base folder on your SSD.")
            return

        steamapps = Path(sa_str)
        if steamapps.name != "steamapps":
            ok = self._confirm(
                "Confirm steamapps",
                f"Selected directory does not end with 'steamapps':\n{steamapps}\n\nProceed anyway?",
            )
            if not ok:
                return

        if not steamapps.exists() or not steamapps.is_dir():
            messagebox.showerror("Invalid path", f"Not a directory: {steamapps}")
            return

        dest_base = Path(dest_base_str)
        ensure_dir(dest_base)

        # Create a unique subfolder per library, named after parent of steamapps
        lib_name = steamapps.parent.name or "steam_library"
        target_root = dest_base / f"{lib_name}_symlink"
        ensure_dir(target_root)

        plan = [("downloading", True)]
        if self.link_temp_var.get():
            plan.append(("temp", True))

        summary_lines = [
            f"Library steamapps: {steamapps}",
            f"Target root on SSD: {target_root}",
        ]
        for sub, _ in plan:
            summary_lines.append(f"  - {sub}: {steamapps/sub} -> {target_root/sub}")

        if not self._confirm("Proceed?", "This will create/replace symlinks as follows:\n\n" + "\n".join(summary_lines)):
            return

        for sub, _ in plan:
            link_path = steamapps / sub
            target_path = target_root / sub
            ensure_dir(target_path)

            # Handle existing link_path
            if link_path.is_symlink():
                if is_symlink_to(link_path, target_path):
                    self._append_log(f"OK: {link_path} already links to {target_path}")
                    continue
                else:
                    if not self._confirm(
                        "Replace symlink",
                        f"{link_path} is a symlink to a different target. Replace it?",
                    ):
                        self._append_log(f"Skipped replacing symlink: {link_path}")
                        continue
                    link_path.unlink()
                    success, message = create_symlink_safe(link_path, target_path)
                    if success:
                        self._append_log(f"Replaced symlink: {link_path} -> {target_path}")
                    else:
                        self._append_log(f"ERROR: {message}")
                        messagebox.showerror("Symlink Error", message)
                    continue

            if link_path.exists():
                if link_path.is_dir():
                    if dir_is_empty(link_path):
                        # Remove empty dir and link
                        link_path.rmdir()
                        success, message = create_symlink_safe(link_path, target_path)
                        if success:
                            self._append_log(f"Linked (empty replaced): {link_path} -> {target_path}")
                        else:
                            self._append_log(f"ERROR: {message}")
                            messagebox.showerror("Symlink Error", message)
                    else:
                        # Offer to move contents then link
                        if not self._confirm(
                            "Move contents?",
                            f"{link_path} is a non-empty directory. Move its contents to {target_path} and replace with a symlink?",
                        ):
                            self._append_log(f"Skipped: left existing directory: {link_path}")
                            continue
                        move_dir_contents(link_path, target_path)
                        # Remove the now-empty directory
                        try:
                            link_path.rmdir()
                        except OSError:
                            # Fallback in case hidden files remain
                            shutil.rmtree(link_path)
                        success, message = create_symlink_safe(link_path, target_path)
                        if success:
                            self._append_log(f"Moved contents and linked: {link_path} -> {target_path}")
                        else:
                            self._append_log(f"ERROR: {message}")
                            messagebox.showerror("Symlink Error", message)
                else:
                    messagebox.showerror("Path exists and is not a directory", str(link_path))
                    self._append_log(f"ERROR: Path exists and is not a directory: {link_path}")
                    continue
            else:
                # Create new symlink
                success, message = create_symlink_safe(link_path, target_path)
                if success:
                    self._append_log(f"Linked: {link_path} -> {target_path}")
                else:
                    self._append_log(f"ERROR: {message}")
                    messagebox.showerror("Symlink Error", message)

        messagebox.showinfo("Done", "Requested symlinks processed. Check the log for details.")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
