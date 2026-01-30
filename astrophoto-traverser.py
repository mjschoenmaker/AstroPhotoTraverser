import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import csv
import re
from pathlib import Path
from threading import Thread

# --- GLOBAL CONFIGURATION ---
FILTER_KEYWORDS = {
    'lextreme': 'L-Extreme',
    'l-pro': 'L-Pro',
    'uvir': 'UV/IR Cut',
    'uv/ir': 'UV/IR Cut',
    'ha': 'Ha',
    'oiii': 'OIII',
    'sii': 'SII',
    'cls': 'CLS'
}

FILE_REGEX = re.compile(
    r'_(?P<exp>[\d.]+)s'           # 180.0s
    r'_Bin(?P<bin>\d+)'            # Bin1
    r'_(?P<camera>[^_]+)'          # 294MC
    r'_gain(?P<gain>\d+)'          # gain120
    r'_(?P<timestamp>\d{8}-\d{6})' # 20250405-214232
    r'_(?P<temp>-?[\d.]+)C'        # -10.0C
)

# Matches folder names starting with YYYYMMDD or YYYY-MM-DD (also allows underscores)
DATE_FOLDER_RE = re.compile(r'^\d{4}[-_]?\d{2}[-_]?\d{2}')

class AstroScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Astro-Inventory Manager")
        self.geometry("700x500")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # UI Layout
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="Astrophotography Drive Scanner", font=("Arial", 24, "bold"))
        self.label.pack(pady=20)

        self.desc = ctk.CTkLabel(self, text="Select the root folder containing your #DSO targets.")
        self.desc.pack(pady=5)

        self.dir_button = ctk.CTkButton(self, text="Browse Hard Drive", command=self.select_dir)
        self.dir_button.pack(pady=10)

        self.path_display = ctk.CTkLabel(self, text="No folder selected", text_color="gray")
        self.path_display.pack(pady=5)

        self.scan_button = ctk.CTkButton(self, text="Start Scan & Create CSV", 
                                          command=self.start_scan_thread, state="disabled",
                                          fg_color="#2ecc71", hover_color="#27ae60")
        self.scan_button.pack(pady=20)

        self.status_box = ctk.CTkTextbox(self, width=600, height=200)
        self.status_box.pack(pady=10)

        self.selected_path = ""

    def log(self, message):
        def _append():
            try:
                self.status_box.insert("end", f"{message}\n")
                self.status_box.see("end")
            except Exception:
                pass
        # Schedule UI update on main thread
        try:
            self.after(0, _append)
        except Exception:
            _append()

    def select_dir(self):
        self.selected_path = filedialog.askdirectory()
        if self.selected_path:
            self.path_display.configure(text=self.selected_path, text_color="white")
            self.scan_button.configure(state="normal")
            self.log(f"Target set to: {self.selected_path}")

    def identify_filter(self, folder_name):
        folder_lower = folder_name.lower()
        for key, formal_name in FILTER_KEYWORDS.items():
            if key in folder_lower:
                return formal_name
        return "Broadband/Unknown"

    def start_scan_thread(self):
        # Run in a separate thread so the GUI doesn't freeze
        Thread(target=self.run_logic).start()

    def run_logic(self):
        # Schedule UI changes on main thread
        try:
            self.after(0, lambda: self.scan_button.configure(state="disabled"))
        except Exception:
            try:
                self.scan_button.configure(state="disabled")
            except Exception:
                pass
        self.log("Initializing scan...")
        
        data_rows = []
        try:
            # Look for fits and fit files
            file_list = list(Path(self.selected_path).rglob('*.fit*'))
            total_files = len(file_list)
            self.log(f"Found {total_files} FITS files. Processing...")

            for idx, path in enumerate(file_list, start=1):
                file_name = path.name

                # Extract path components relative to selected root
                try:
                    rel_parts = path.relative_to(Path(self.selected_path)).parts
                    num_parts = len(rel_parts)
                    if num_parts >= 3:
                        obj_name = rel_parts[0]
                        if num_parts == 3:
                            telescope = ''
                            session_info = rel_parts[1]
                        else:  # num_parts >= 4
                            telescope = rel_parts[1]
                            session_info = rel_parts[2]
                    else:
                        obj_name = ''
                        telescope = ''
                        session_info = path.parent.name if path.parent else ''
                except ValueError:
                    # If relative_to fails, fall back to old method
                    session_info = path.parent.name if path.parent is not None else ''
                    telescope = path.parent.parent.name if path.parent and path.parent.parent else ''
                    obj_name = path.parent.parent.parent.name if path.parent and path.parent.parent and path.parent.parent.parent else ''

                # Try the strict regex first, fall back to tolerant searches
                match = FILE_REGEX.search(file_name)
                if match:
                    meta = match.groupdict()
                else:
                    meta = {}
                    # tolerant individual field searches
                    exp_m = re.search(r'(?P<exp>[\d.]+)s', file_name)
                    bin_m = re.search(r'Bin(?P<bin>\d+)', file_name, re.IGNORECASE)
                    gain_m = re.search(r'gain(?P<gain>\d+)', file_name, re.IGNORECASE)
                    ts_m = re.search(r'(?P<timestamp>\d{8}-\d{6})', file_name)
                    temp_m = re.search(r'(?P<temp>-?[\d.]+)C', file_name)

                    if exp_m:
                        meta['exp'] = exp_m.group('exp')
                    if bin_m:
                        meta['bin'] = bin_m.group('bin')
                    if gain_m:
                        meta['gain'] = gain_m.group('gain')
                    if ts_m:
                        meta['timestamp'] = ts_m.group(0)
                    if temp_m:
                        meta['temp'] = temp_m.group('temp')

                    # Attempt to identify camera token: look through underscore-separated tokens
                    if 'camera' not in meta:
                        tokens = [t for t in re.split(r'[_\-]', file_name) if t]
                        # find first token that looks like a camera id (letters+digits) and is not matched above
                        for t in tokens:
                            if re.match(r'^[A-Za-z0-9]+$', t) and not re.search(r'Bin\d+|gain\d+|\d{8}|\d+s', t, re.IGNORECASE):
                                meta['camera'] = t
                                break

                # If still missing major metadata, log a skipped-file note but still include minimal info
                if not meta:
                    self.log(f"Note: filename did not match expected patterns: {file_name}")

                # Only include files whose immediate parent folder starts with a date (YYYYMMDD or YYYY-MM-DD)
                parent_name = (session_info or '').strip()
                if not DATE_FOLDER_RE.match(parent_name):
                    # occasionally log skipped non-date folders
                    if idx % 100 == 0:
                        self.log(f"Skipping file not in date folder: {file_name} (parent='{session_info}')")
                    continue

                # Additionally, only include FIT files that start with "Light_"
                if not file_name.startswith("Light_"):
                    continue

                row = {
                    'Object': obj_name or 'Unknown',
                    'Filter': self.identify_filter(session_info or ''),
                    'Camera': meta.get('camera', 'N/A'),
                    'Telescope': telescope or 'Unknown',
                    'Exposure': meta.get('exp', '0'),
                    'Bin': meta.get('bin', '1'),
                    'Gain': meta.get('gain', '0'),
                    'Temp': meta.get('temp', '0'),
                    'Timestamp': meta.get('timestamp', ''),
                    'Session Folder': session_info or '',
                    'Processed': 'No',
                    'Path': str(path)
                }
                data_rows.append(row)

                # Progress logging every 50 files
                if idx % 50 == 0 or idx == total_files:
                    pct = (idx / total_files) * 100 if total_files else 100
                    self.log(f"Processed {idx}/{total_files} files ({pct:.1f}%)")

            # If nothing was indexed, inform the user and skip creating CSV
            if not data_rows:
                self.log("No FITS files indexed; CSV not created.")
                try:
                    self.after(0, lambda: messagebox.showinfo("Done", "No FITS files found; CSV not created."))
                except Exception:
                    messagebox.showinfo("Done", "No FITS files found; CSV not created.")
                try:
                    self.after(0, lambda: self.scan_button.configure(state="normal"))
                except Exception:
                    try:
                        self.scan_button.configure(state="normal")
                    except Exception:
                        pass
                return

            # Save to CSV in the same folder as the script
            output_file = os.path.join(os.getcwd(), "astro_inventory.csv")
            keys = data_rows[0].keys()
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(data_rows)

            self.log(f"SUCCESS: {len(data_rows)} files indexed.")
            self.log(f"Saved to: {output_file}")
            try:
                self.after(0, lambda: messagebox.showinfo("Done", f"Scan complete!\nCSV saved to: {output_file}"))
            except Exception:
                messagebox.showinfo("Done", f"Scan complete!\nCSV saved to: {output_file}")

        except Exception as e:
            self.log(f"ERROR: {str(e)}")
            try:
                self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))
            except Exception:
                messagebox.showerror("Error", f"An error occurred: {e}")

        # Ensure the scan button is re-enabled on the main thread
        try:
            self.after(0, lambda: self.scan_button.configure(state="normal"))
        except Exception:
            try:
                self.scan_button.configure(state="normal")
            except Exception:
                pass

if __name__ == "__main__":
    app = AstroScannerApp()
    app.mainloop()