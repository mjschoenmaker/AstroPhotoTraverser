import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import csv
import re
from pathlib import Path
from threading import Thread

import config

class AstroScannerCore:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log = log_callback or (lambda x: None)
        self.progress = progress_callback or (lambda x, y: None)
        self.session_to_camera = {}
        self.session_to_filter = {}
        self.session_to_gain = {}
        self.session_to_exp = {}
        self.session_to_temp = {} 
        # Cache edit status to avoid redundant folder scans
        self.folder_edit_cache = {}

    # does the folder contain any files that indicate the images may have been edited (e.g., TIF, PSD, or files with "stack" in the name)? If so, we will skip metadata extraction for all files in that folder since edits often break naming conventions and metadata patterns.
    def _has_edits(self, folder_path):
        """Helper to check if a folder contains TIF, PSD, or 'stack' files."""
        if not folder_path or folder_path == '.':
            return False
            
        path_str = str(folder_path)
        if path_str in self.folder_edit_cache:
            return self.folder_edit_cache[path_str]

        try:
            p = Path(folder_path)
            if not p.exists():
                return False
                
            # Define our patterns
            extensions = {'.tif', '.tiff', '.psd'}
            
            # Use rglob('*') to look into all subdirectories recursively
            # We use a generator to exit as soon as we find a single matching file
            for file in p.rglob('*'):
                if not file.is_file():
                    continue
                    
                name_lower = file.name.lower()
                if file.suffix.lower() in extensions or "stack" in name_lower:
                    # if file is a calibration frame, we should ignore edits in that folder since it's common to have stacks and edits in calibration folders but it doesn't necessarily mean the light frames are edited.
                    if "darks" in name_lower or "bias" in name_lower or "flat" in name_lower:
                        self.log(f"Ignoring calibration edits in '{folder_path}' (found: {file.relative_to(p)})")
                        return False
                    else:
                        self.log(f"Detected edits in '{folder_path}' (found: {file.relative_to(p)})")
                        self.folder_edit_cache[path_str] = True
                        return True
                    
        except Exception as e:
            self.log(f"Error scanning for edits in {folder_path}: {e}")
            
        self.folder_edit_cache[path_str] = False
        return False

    def scan_folder(self, root_path):
        # The core engine that traverses files and extracts metadata.
        root = Path(root_path)
        fit_files = list(root.rglob('*.fit*'))
        cr2_files = list(root.rglob('*.cr2'))
        dng_files = list(root.rglob('*.dng'))
        jpg_files = list(root.rglob('*.jpg'))
        jpeg_files = list(root.rglob('*.jpeg'))
        file_list = fit_files + cr2_files + dng_files + jpg_files + jpeg_files

        data_rows = []
        total_files = len(file_list)
        for idx, path in enumerate(file_list, start=1):
            row = self._extract_metadata(path, root)
            if row:
                data_rows.append(row)
            
            # Send the update to the UI every 50 files
            if idx % 50 == 0 or idx == total_files:
                self.progress(idx, total_files)      
        
        return data_rows
    
    def save_to_csv(self, data_rows, output_path):
        """Handles the file IO for CSV generation."""
        if not data_rows:
            return
        keys = data_rows[0].keys()
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_rows)

    # This method is the heart of the metadata extraction logic. It takes a file path and the root directory, and returns a dictionary of extracted metadata.
    def _extract_metadata(self, path, root):
        file_name = path.name
        is_fit = file_name.lower().endswith(('.fit', '.fits'))

        # Extract path components relative to selected root
        try:
            rel_parts = path.relative_to(Path(root)).parts
            num_parts = len(rel_parts)
            if num_parts >= 3:
                obj_name = rel_parts[0]
                if num_parts == 3:
                    telescope = 'missing info'
                    session_info = rel_parts[1]
                else:  # num_parts >= 4
                    # in case of missing telescope folder, we are likely to have to treat rel_parts[1] as session and leave telescope empty.
                    if config.DATE_FOLDER_RE.match(rel_parts[1]):
                        telescope = 'missing info'
                        session_info = rel_parts[1]
                    else:
                        telescope = rel_parts[1]
                        session_info = rel_parts[2]
            else:
                obj_name = ''
                telescope = 'missing info'
                session_info = path.parent.name if path.parent else ''
        except ValueError:
            # If relative_to fails, fall back to old method
            session_info = path.parent.name if path.parent is not None else ''
            telescope = path.parent.parent.name if path.parent and path.parent.parent else 'missing info'
            obj_name = path.parent.parent.parent.name if path.parent and path.parent.parent and path.parent.parent.parent else ''

        # Check both the session folder (parent) and the object folder (grandparent) for signs of edits.
        session_path = path.parent
        object_path = session_path.parent if session_path else None
        
        has_edits = "No"
        if self._has_edits(session_path) or self._has_edits(object_path):
            has_edits = "Yes"

        # Only include files whose immediate parent folder starts with a date (YYYYMMDD or YYYY-MM-DD)
        parent_name = (session_info or '').strip()
        if not config.DATE_FOLDER_RE.match(parent_name):
            self.log(f"Skipping file not in date folder: {file_name} (parent='{session_info}')")
            return

        # Additionally, only include image files that start with "Preview_", "Light_", "CRW_", or "IMG_" 
        lower_path_str = str(path).lower()
        if not (file_name.startswith("Preview_") or file_name.startswith("Light_") or file_name.startswith("CRW_") or file_name.startswith("IMG_")):
            return
        # Additionaly skip ASIAIR thumbnail files that end in _thn.jpg
        if file_name.endswith("_thn.jpg"):
            return
        
        # or that reside in a folder that include "darks","bias" or "flats"
        if any(keyword in lower_path_str for keyword in ["darks", "bias", "flats"]):
            return

        # Try the strict regex first, fall back to tolerant searches
        match = config.FILE_REGEX.search(file_name)
        if match:
            meta = match.groupdict()
            # Invalidate camera if it matches invalid patterns (e.g., starts with 'gain')
            if meta.get('camera') and re.match(r'gain\d+', meta['camera'], re.IGNORECASE):
                meta['camera'] = None
        else:
            meta = {}
            # tolerant individual field searches
            exp_m = re.search(r'(?P<exp>[\d.]+)s', file_name)
            bin_m = re.search(r'Bin(?P<bin>\d+)', file_name, re.IGNORECASE)
            gain_m = re.search(r'gain(?P<gain>\d+)', file_name, re.IGNORECASE)
            ts_m = re.search(r'(?P<timestamp>\d{8}-\d{6})', file_name)
            temp_m = re.search(r'_(?P<temp>-?[\d]+(?:\.[\d]+)?)C', file_name)
            rot_m = re.search(r'_(?P<rotation>\d+)deg', file_name)

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
            if rot_m:
                meta['rotation'] = rot_m.group('rotation')

            # Attempt to identify camera token: look for token after Bin
            if 'camera' not in meta:
                tokens = [t for t in re.split(r'[_\-]', file_name) if t]
                bin_indices = [i for i, t in enumerate(tokens) if re.match(r'Bin\d+', t, re.IGNORECASE)]
                if bin_indices:
                    bin_idx = bin_indices[0]
                    if bin_idx + 1 < len(tokens):
                        candidate = tokens[bin_idx + 1]
                        if re.match(r'^[A-Za-z0-9]+$', candidate):
                            meta['camera'] = candidate

            # Invalidate camera if it starts with ISO followed by digits
            if meta.get('camera') and re.match(r'ISO\d+', meta['camera'], re.IGNORECASE):
                meta['camera'] = None
            
            # Invalidate camera if it starts with gain followed by digits
            if meta.get('camera') and re.match(r'gain\d+|\d{8}|\d+s', meta['camera'], re.IGNORECASE):
                meta['camera'] = None

            # Invalidate camera if it actually is a filter name
            if meta.get('camera') and meta['camera'].lower() in config.FILTER_KEYWORDS:
                meta['filter'] = config.identify_filter(meta['camera'])  # move value to filter
                meta['camera'] = None

            # Try to get filter from filename, when one of filter_keywords delimited by _ is found.
            if not meta.get('filter'):
                for key, formal_name in config.FILTER_KEYWORDS.items():
                    if re.search(r'[_\-]' + re.escape(key) + r'[_\-]', file_name, re.IGNORECASE):
                        meta['filter'] = formal_name
                        break

        # Use cached camera from session if available
        if not meta.get('camera') and session_info in self.session_to_camera:
            meta['camera'] = self.session_to_camera[session_info]
        elif meta.get('camera'):
            self.session_to_camera[session_info] = meta['camera']

        # Use cached gain from session if available
        if not meta.get('gain') and session_info in self.session_to_gain:
            meta['gain'] = self.session_to_gain[session_info]
        # Use cached exposure time from session if available
        if not meta.get('exp') and session_info in self.session_to_exp:
            meta['exp'] = self.session_to_exp[session_info]
        # Use cached temperature from session if available
        if not meta.get('temp') and session_info in self.session_to_temp:
            meta['temp'] = self.session_to_temp[session_info]
        # Use cached filter from session if available
        if not meta.get('filter') and session_info in self.session_to_filter:
            meta['filter'] = self.session_to_filter[session_info]

        # Try to read missing info from FITS header (only for FIT files that pass checks)
        if is_fit and config.FITS_AVAILABLE and (
            not meta.get('camera')  
            or not meta.get('gain')
            or not meta.get('temp')
            or not meta.get('filter')
            ):
            try:
                with config.fits.open(str(path), mode='readonly') as hdul:
                    header = hdul[0].header
                    camera = header.get('INSTRUME') or header.get('CAMERA') or header.get('TELESCOP')
                    gain = header.get('GAIN')
                    temp = header.get('CCD-TEMP') or header.get('SET-TEMP')
                    filter_name = header.get('FILTER')
                    with open('debug.log', 'a') as f:
                        f.write(f"Fits header read for {file_name}: camera={camera}, gain={gain}, temp={temp}, filter={filter_name}\n")
                    if camera:
                        meta['camera'] = camera
                        self.session_to_camera[session_info] = meta['camera']  # update cache
                    if filter_name:
                        meta['filter'] = config.identify_filter(filter_name) 
                        # not cacheing filter because it can change within a session, but we can still identify it for this file
                    if gain:
                        meta['gain'] = gain
                        self.session_to_gain[session_info] = meta['gain']  # update cache
                    if temp:
                        meta['temp'] = temp
                        self.session_to_temp[session_info] = meta['temp']  # update cache
            except Exception as e:
                with open('debug.log', 'a') as f:
                    f.write(f"Failed to read fits header for {file_name}: {e}\n")

        # Try to read missing camera from EXIF (for non-FIT files)
        if not is_fit and config.EXIF_AVAILABLE and not meta.get('camera'):
            try:
                with open(str(path), 'rb') as f:
                    tags = config.exifread.process_file(f)
                    camera = tags.get('Image Model') or tags.get('EXIF Model')
                    with open('debug.log', 'a') as f:
                        f.write(f"Exif header read for {file_name}: camera={camera}\n")
                    if camera:
                        meta['camera'] = str(camera)
                        self.session_to_camera[session_info] = meta['camera']  # update cache
                    # Also try to get ISO for gain if missing and not cached for session
                    if not meta.get('gain') and session_info not in self.session_to_gain:
                        iso = tags.get('EXIF ISOSpeedRatings')
                        if iso:
                            meta['gain'] = str(iso)
                            self.session_to_gain[session_info] = meta['gain']  # cache gain
                    # Also try to get exposure time if missing and not cached for session
                    if not meta.get('exp') and session_info not in self.session_to_exp:
                        exp_time = tags.get('EXIF ExposureTime')
                        if exp_time:
                            # Convert exposure time to seconds (e.g., "1/30" -> "0.0333")
                            exp_str = str(exp_time)
                            if '/' in exp_str:
                                num, den = exp_str.split('/')
                                try:
                                    exp_seconds = float(num) / float(den)
                                    meta['exp'] = f"{exp_seconds:.4f}".rstrip('0').rstrip('.')
                                    self.session_to_exp[session_info] = meta['exp']  # cache exposure
                                except ValueError:
                                    pass
                            else:
                                # Already in seconds format
                                meta['exp'] = exp_str
                                self.session_to_exp[session_info] = meta['exp']  # cache exposure
                    # Also try to get temperature if missing and not cached for session
                    if not meta.get('temp') and session_info not in self.session_to_temp:
                        temp_tag = tags.get('EXIF CameraTemperature') or tags.get('EXIF AmbientTemperature') or tags.get('EXIF SensorTemperature')
                        if temp_tag:
                            meta['temp'] = str(temp_tag)
                            self.session_to_temp[session_info] = meta['temp']  # cache temperature
            except Exception as e:
                with open('debug.log', 'a') as f:
                    f.write(f"Failed to read exif header for {file_name}: {e}\n")

        # As a last resort, try to identify filter from session folder name if not found in filename or FITS header
        if not meta.get('filter') or meta['filter'] in [None, 'Broadband/Unknown']:
            meta['filter'] = config.identify_filter(session_info)
            # cache filter if succesfully identified from session folder, since it's likely consistent for the session
            if meta['filter'] not in [None, 'Broadband/Unknown']:
                self.session_to_filter[session_info] = meta['filter']
       
        # If still missing major metadata, log a skipped-file note but still include minimal info
        if not meta:
            self.log(f"Note: filename did not match expected patterns: {file_name}")

        return {
            'Object': obj_name or 'Unknown',
            'Filter': meta.get('filter', 'Broadband/Unknown'),
            'Camera': meta.get('camera', ''),
            'Telescope': telescope or '',
            'Exposure': meta.get('exp', '0'),
            'Bin': meta.get('bin', '1'),
            'Gain': meta.get('gain', ''),
            'Temp': meta.get('temp', ''),
            'Rotation': meta.get('rotation', ''),
            'Timestamp': meta.get('timestamp', ''),
            'Session Folder': session_info or '',
            'Edits Detected': has_edits,
            'Path': str(path)
        }


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

        # --- Hidden UI Elements (Progress) ---
        self.progress_label = ctk.CTkLabel(self, text="Initializing...")
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        
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

    def update_progress(self, current, total):
        """Updates the progress bar from 0.0 to 1.0"""
        if total > 0:
            fraction = current / total
            percentage = int(fraction * 100)
            # .after(0, ...) ensures the UI update happens on the main thread
            self.after(0, lambda: self.progress_bar.set(fraction))
            self.after(0, lambda: self.progress_label.configure(text=f"Progress: {percentage}% ({current}/{total})"))

    def select_dir(self):
        self.selected_path = filedialog.askdirectory()
        if self.selected_path:
            self.path_display.configure(text=self.selected_path, text_color="white")
            self.scan_button.configure(state="normal")
            self.log(f"Target set to: {self.selected_path}")
            
            # hide the progress elements until scan starts
            self.progress_label.pack_forget()
            self.progress_bar.pack_forget()
            
            # empty the status box
            self.status_box.delete("1.0", "end")

    def start_scan_thread(self):
        # 1. Show the progress elements before starting
        self.progress_label.configure(text="Initializing...")
        self.progress_label.pack(pady=(10, 0), after=self.scan_button)
        self.progress_bar.pack(pady=(5, 10), after=self.progress_label)
        self.progress_bar.set(0)
        
        if not hasattr(self, 'selected_path') or not self.selected_path:
            self.after(0, lambda: messagebox.showwarning("Warning", "Please select a folder first!"))
            return
    
        # Start the background thread
        thread = Thread(target=self.run_logic, daemon=True)
        thread.start()

    def run_logic(self):
        import sys
        with open('debug.log', 'a') as f:
            f.write(f"Python executable: {sys.executable}\n")
            f.write(f"FITS_AVAILABLE: {config.FITS_AVAILABLE}\n")
            f.write(f"EXIF_AVAILABLE: {config.EXIF_AVAILABLE}\n")

        # 1. Update UI state to 'Processing' mode
        self.after(0, lambda: self.scan_button.configure(state="disabled"))
        self.log("Initializing scan...")

        # 2. Instantiate the logic engine with callbacks 
        # This allows the logic to 'talk' to the UI without being 'part' of it
        core = AstroScannerCore(
            log_callback=self.log,
            progress_callback=self.update_progress
        )

        try:
            # 3. Execute logic
            data = core.scan_folder(self.selected_path)
            if not data:
                self.after(0, lambda: messagebox.showwarning("No Data", "No compatible files were found."))
                return

            # 4. Save results        
            output_file = os.path.join(os.getcwd(), "astro_inventory.csv")
            core.save_to_csv(data, output_file)
            
            # 5. Notify UI of completion
            self.log(f"SUCCESS: {len(data)} files indexed.")
            self.after(0, lambda: messagebox.showinfo("Done", f"Scan complete!\nSaved to: {output_file}"))
        
        except Exception as e:
            # 6. Error handling
            self.log(f"ERROR: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))

            # 7. Ensure scan button is re-enabled even if error occurs
        finally:
            self.after(0, lambda: self.scan_button.configure(state="normal"))

if __name__ == "__main__":
    app = AstroScannerApp()
    app.mainloop()