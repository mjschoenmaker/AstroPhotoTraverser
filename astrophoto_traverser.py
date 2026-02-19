import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import csv
import re
import time
from pathlib import Path
from threading import Thread
from dataclasses import dataclass, fields
from typing import Optional

import config

@dataclass
class SessionMetadata:
    camera: Optional[str] = None
    filter: Optional[str] = None
    gain: Optional[str] = None
    exposure: Optional[str] = None
    temperature: Optional[str] = None

class AstroScannerCore:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log = log_callback or (lambda x: None)
        self.progress = progress_callback or (lambda x, y: None)
        # Cache values to avoid redundant folder scans using the SessionMetaData dataclass
        self.session_cache: dict[str, SessionMetadata] = {}
        self.folder_edit_cache = {}
        self.stop_requested = False # Flag to signal stopping the scan if needed

        # Map the extraction methods
        method_map = {
            'fits': self._get_metadata_from_fits_header,
            'exif': self._get_metadata_from_exif
        }

        # Map the file extensions to their respective extraction methods based on config
        self._extractors = {
            ext: method_map[ext_type]
            for ext, ext_type in config.FILE_TYPES.items()
        }

    def _sync_session_data(self, meta, session: SessionMetadata):
            """
            Private helper to synchronize found metadata with the session cache.
            If a field is missing in meta, it pulls from the session.
            If a field is present in meta, it updates the session.
            """
            for field in fields(session):
                field_name = field.name
                # 1. Pull from session if current file is missing the value
                if not meta.get(field_name):
                    meta[field_name] = getattr(session, field_name)
                
                # 2. Update session if we found a value (from filename or header)
                if meta.get(field_name):
                    setattr(session, field_name, meta[field_name])

    def scan_folder(self, root_path):
        root = Path(root_path)
        valid_extensions = config.FILE_TYPES.keys()
        edit_indicators = {'.tif', '.tiff', '.psd'}
        
        file_list = []
        data_rows = []
        
        self.log("Reading the directory tree...")

        # os.walk is often faster for large trees than Path.rglob
        for current_dir, dirs, files in os.walk(root_path):
            if self.stop_requested:
                return []

            curr_p = Path(current_dir)
            
            # 1. Check for edits in this specific folder (Shallow check)
            if self._has_edits_in_folder(files, current_dir):
                # and if found, mark this folder and all parents up to the root in the cache as containing edits
                self._bubble_up_edit_status(curr_p, root)

            # 2. Collect image files from this folder
            for f in files:
                file_path = curr_p / f
                if file_path.suffix.lower() in valid_extensions:
                    file_list.append(file_path)

        total_files = len(file_list)
        self.log(f"Found {total_files} images. Extracting metadata...")

        for idx, path in enumerate(file_list, start=1):
            if self.stop_requested:
                return []

            row = self._extract_metadata(path, root)
            if row:
                data_rows.append(row)
            
            if idx % 50 == 0 or idx == total_files:
                self.progress(idx, total_files)      
        
        return data_rows

    def _bubble_up_edit_status(self, start_path, root_limit):
        """Recursively marks parent folders as containing edits up to the root."""
        temp_p = start_path
        while temp_p != root_limit and temp_p != temp_p.parent:
            self.folder_edit_cache[str(temp_p)] = True
            temp_p = temp_p.parent

    def _has_edits_in_folder(self, files, current_dir):
        """
        Encapsulates the logic for detecting image edits or stacked results.
        Returns True if edit indicators are found and the folder is not a calibration directory.
        """
        edit_indicators = {'.tif', '.tiff', '.psd'}
        
        # 1. Look for edit-related file extensions or "stack" in the filename
        for f in files:
            f_lower = f.lower()
            if any(f_lower.endswith(ext) for ext in edit_indicators) or "stack" in f_lower:
                
                # 2. Exclude calibration folders (darks, bias, flats) from triggering an 'Edit' flag
                if not any(k in current_dir.lower() for k in config.CALIBRATION_KEYWORDS):
                    return True
                    
        return False

    def save_to_csv(self, data_rows, output_path):
        """Handles the file IO for CSV generation."""
        if not data_rows:
            return
        keys = data_rows[0].keys()
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_rows)

    def _get_metadata_from_path(self, path, root):
        """
        Extracts Object, Telescope, and Session info by analyzing the directory 
        hierarchy relative to the scan root.
        """
        try:
            # path.relative_to(root) gives us only the folders inside the selected target
            rel_parts = path.relative_to(Path(root)).parts
            num_parts = len(rel_parts)
            
            # rel_parts index 0 is usually the 'Object' (e.g., M42)
            # The last part is the filename, so we ignore it.
            # We look for the 'Session' (the folder starting with a date)
            
            obj_name = rel_parts[0] if num_parts > 1 else ''
            telescope = 'missing info'
            session_info = ''

            # Find the session folder by checking parts from right to left
            # (excluding the filename at the end)
            for i in range(num_parts - 2, -1, -1):
                if config.DATE_FOLDER_RE.match(rel_parts[i]):
                    session_info = rel_parts[i]
                    # If there's a folder between Object and Session, it's the Telescope
                    if i > 1:
                        telescope = rel_parts[i-1]
                    break
            
            # Fallback if no date folder was found in the relative path
            if not session_info:
                session_info = path.parent.name if path.parent else ''

            return obj_name, telescope, session_info

        except (ValueError, IndexError):
            # Fallback for files outside the root or unexpected structures
            session_info = path.parent.name if path.parent else ''
            telescope = path.parent.parent.name if path.parent and path.parent.parent else 'missing info'
            obj_name = path.parent.parent.parent.name if path.parent and path.parent.parent and path.parent.parent.parent else ''
            return obj_name, telescope, session_info

    def _format_exposure_time(self, exp_time):
        """Converts EXIF exposure time to a consistent string format in seconds."""
        exp_str = str(exp_time)
        if '/' in exp_str:
            num, den = exp_str.split('/')
            try:
                exp_seconds = float(num) / float(den)
                return f"{exp_seconds:.4f}".rstrip('0').rstrip('.')
            except ValueError:
                return exp_str  # Return original if conversion fails
        else:
            return exp_str  # Already in seconds format

    def _get_metadata_from_fits_header(self, path):
        """FITS strategy: returns a dict of metadata."""
        if not config.FITS_AVAILABLE:
            return {}
        try:
            with config.fits.open(str(path), mode='readonly') as hdul:
                header = hdul[0].header # type: ignore
                # Return keys that match our dataclass fields

                raw_filter = header.get('FILTER')
                clean_filter = config.identify_filter(raw_filter) if raw_filter else None
                return {
                    'camera': header.get('INSTRUME') or header.get('CAMERA'),
                    'gain': str(header.get('GAIN', '') or header.get('ISO', '')),
                    'temperature': str(header.get('CCD-TEMP') or header.get('SET-TEMP', '')),
                    'exposure': str(header.get('EXPTIME', '')),
                    'filter': clean_filter
                }
        except Exception as e:
            with open('debug.log', 'a') as f:
                f.write(f"Error reading FITS header for {path}: {e}\n") 
                self.log(f"Error reading FITS header for {path}: {e}")
            return {}

    def _get_metadata_from_exif(self, path):
        """EXIF strategy: returns a dict of metadata."""
        if not config.EXIF_AVAILABLE:
            return {}
        try:
            with open(str(path), 'rb') as f:
                tags = config.exifread.process_file(f)
                return {
                    'camera': str(tags.get('Image Model') or ''),
                    'gain': str(tags.get('EXIF ISOSpeedRatings') or ''),
                    'exposure': self._format_exposure_time(tags.get('EXIF ExposureTime')),
                    'temperature': str(tags.get('EXIF CameraTemperature') or '')
                }
        except Exception as e:
            with open('debug.log', 'a') as f:
                f.write(f"Error reading EXIF data for {path}: {e}\n")
                self.log(f"Error reading EXIF data for {path}: {e}")
            return {}

    def _get_medata_from_filename(self, file_name):
        """Filename parsing strategy: returns a dict of metadata."""
        meta = {}
        # Try the strict regex first, fall back to tolerant searches
        match = config.FILE_REGEX.search(file_name)
        if match:
            meta = match.groupdict()
        else:
            meta = self._fallback_token_search(file_name)

        return meta

    def _fallback_token_search(self, file_name):
        """
        Performs tolerant, individual regex searches for metadata when 
        the main FILE_REGEX fails.
        """
        meta = {}
        
        # 1. Search for specific patterns independently
        patterns = {
            'exposure': r'(?P<v>[\d.]+)s',
            'bin': r'Bin(?P<v>\d+)',
            'gain': r'(?:gain|ISO)(?P<v>\d+)',
            'temperature': r'_(?P<v>-?[\d]+(?:\.[\d]+)?)C',
            'rotation': r'_(?P<v>\d+)deg',
            'timestamp': r'(?P<v>\d{8}-\d{6})'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, file_name, re.IGNORECASE)
            if match:
                meta[key] = match.group('v')

        # 2. Attempt to identify camera token
        # Look for a alphanumeric token immediately following the 'Bin' marker
        tokens = [t for t in re.split(r'[_\-]', file_name) if t]
        bin_indices = [i for i, t in enumerate(tokens) if re.match(r'Bin\d+', t, re.IGNORECASE)]
        
        if bin_indices:
            bin_idx = bin_indices[0]
            if bin_idx + 1 < len(tokens):
                candidate = tokens[bin_idx + 1]
                # If the next token looks like a camera name (alphanumeric only)
                if re.match(r'^[A-Za-z0-9]+$', candidate):
                    meta['camera'] = candidate

        return meta

    def _cleanup_parsed_metadata(self, meta, file_name):
        """
        Sanitizes raw metadata extracted from filenames. 
        Handles invalid patterns and cross-field mapping (e.g., camera vs. filter).
        """

        camera = meta.get('camera')
        # 1. Invalidate camera if it matches non-camera patterns (e.g., 'gain120' or timestamps)
        if camera:
            is_timestamp = re.match(r'^\d{8}$|^\d{8}-\d{6}$', camera)
            is_gain_iso = re.match(r'^(gain|ISO)\d+', camera, re.IGNORECASE)

            if is_timestamp or is_gain_iso:
                meta['camera'] = None

        # 2. Invalidate camera if it is actually a known filter name
        if camera and str(camera).lower() in config.FILTER_KEYWORDS:
            # Move the value to filter if we don't have one yet
            if not meta.get('filter'):
                meta['filter'] = config.identify_filter(meta['camera'])
            meta['camera'] = None

        # 3. Last-ditch attempt to find filter in the filename if still missing
        if not meta.get('filter'):
            for key, formal_name in config.FILTER_KEYWORDS.items():
                # Look for filter keywords delimited by underscores or dashes
                if re.search(r'[_\-]' + re.escape(key) + r'[_\-]', file_name, re.IGNORECASE):
                    meta['filter'] = formal_name
                    break
                    
        return meta

    def _is_valid_file(self, path, session_info):
        file_name = path.name
        # Only include files whose immediate parent folder starts with a date (YYYYMMDD or YYYY-MM-DD)
        parent_name = (session_info or '').strip()
        if not config.DATE_FOLDER_RE.match(parent_name):
            self.log(f"Skipping file not in date folder: {file_name} (parent='{session_info}')")
            return False

        # Only include image files that start with "Preview_", "Light_", "CRW_", or "IMG_" and don't end with "_thn.jpg"
        if not file_name.startswith(config.ALLOWED_FILE_PREFIXES) or file_name.endswith(config.SKIPPED_FILE_SUFFIXES):
            self.log(f"Skipping file: {file_name} (parent='{session_info}')")
            return False
        
        # or that reside in a folder that indicate calibration frames (e.g., "darks", "bias", "flats")
        lower_path_str = str(path).lower()
        if any(keyword in lower_path_str for keyword in config.CALIBRATION_KEYWORDS):
            self.log(f"Skipping calibration file: {file_name} (parent='{session_info}')")
            return False
        
        return True

    def _needs_header_extraction(self, meta):
        """
        Returns True if critical metadata is missing. 
        As configured in config.REQUIRED_METADATA_FIELDS.
        """
        return any(not meta.get(field) for field in config.REQUIRED_METADATA_FIELDS)

    def _extract_metadata(self, path, root):
        """
        Extracts metadata from the file using multiple strategies:
        1. Basic metadata from the file path structure (Object, Telescope, Session)
        2. Validation based on naming and folder conventions
        3. Metadata from the filename using regex and keyword searches
        4. Metadata from the file header using the appropriate extractor based on file extension
        5. Syncing metadata with session cache to fill in missing values and ensure consistency
        6. As a last resort, try to identify filter from session folder name if not found in filename or file header
        7. If still missing major metadata, log a skipped-file note but still include minimal info
        8. Formatting the result into a consistent dictionary for CSV output
        """
        file_name = path.name
        session_folder = str(path.parent)  # Cache based on the session folder
        if session_folder not in self.session_cache:
            self.session_cache[session_folder] = SessionMetadata()
        session = self.session_cache[session_folder]

        # 1. Basic metadata from the file path structure (Object, Telescope, Session)
        obj_name, telescope, session_info = self._get_metadata_from_path(path, root)

        # 2. Validation based on naming and folder conventions
        if not self._is_valid_file(path, session_info):
            return None

        # 3. Metadata from the filename using regex and keyword searches
        meta = self._get_medata_from_filename(file_name)

        # Move filter keywords out of the 'camera' field before syncing with session, since they are more likely to be consistent across the session and we want to cache them if found in the filename
        meta = self._cleanup_parsed_metadata(meta, file_name)

        # This pulls values (like camera or filter) already found in previous files.
        self._sync_session_data(meta, session)

        # 4. Conditional Extraction (The "Gatekeeper")
        ext = path.suffix.lower()
        extractor_func = self._extractors.get(ext)
        
        # Check if we are still missing critical info after syncing with session
        if extractor_func and self._needs_header_extraction(meta):
            # Get the metadata from the appropriate extractor
            extracted_meta = extractor_func(path)
            
            # Sync the new findings back to the session cache for the next files
            self._sync_session_data(extracted_meta, session)
            
            # Update meta with any new info found from the file header
            meta.update({k: v for k, v in extracted_meta.items() if v})

        # 5. Syncing metadata with session cache to fill in missing values and ensure consistency
        self._sync_session_data(meta, session)

        # 6. As a last resort, try to identify filter from session folder name if not found in filename or file header
        if not meta.get('filter') or meta['filter'] in [None, 'Broadband/Unknown']:
            meta['filter'] = config.identify_filter(session_info)
            # cache filter if succesfully identified from session folder, since it's likely consistent for the session
            if meta['filter'] not in [None, 'Broadband/Unknown']:
                session.filter = meta['filter']
       
        # 7. If still missing major metadata, log a skipped-file note
        if not meta:
            self.log(f"Note: filename did not match expected patterns: {file_name}")
            return

        # 8. Formatting the result
        return self._build_result_row(path, meta, obj_name, telescope, session_info)

    def _build_result_row(self, path, meta, obj_name, telescope, session_info):
        # Check both the session folder (parent) and the object folder (grandparent) for signs of edits.
        session_path_str = str(path.parent)
        object_path_str = str(path.parent.parent) if path.parent else None

        # O(1) Lookup from the cache we built during the walk
        has_edits = "No"
        if self.folder_edit_cache.get(session_path_str) or self.folder_edit_cache.get(object_path_str):
            has_edits = "Yes"

        return {
            'Object': obj_name or 'Unknown',
            'Filter': meta.get('filter', 'Broadband/Unknown'),
            'Camera': meta.get('camera', ''),
            'Telescope': telescope or '',
            'Exposure': meta.get('exposure', '0'),
            'Bin': meta.get('bin', '1'),
            'Gain': meta.get('gain', ''),
            'Temp': meta.get('temperature', ''),
            'Rotation': meta.get('rotation', ''),
            'Timestamp': meta.get('timestamp', ''),
            'Session Folder': session_info or '',
            'Edits Detected': has_edits,
            'Path': str(path)
        }


class AstroScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Bind the Escape key to allow users to stop the scan
        self.bind('<Escape>', self.request_stop)
        self.core = None  # Will hold the AstroScannerCore instance   

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

    def request_stop(self, event=None):
        if self.core:
            self.log("Stop requested. Attempting to halt the scan...")
            self.core.stop_requested = True

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

        # 1. Update UI state to 'Initializing' mode
        self.after(0, lambda: self.scan_button.configure(state="disabled"))
        self.log("Initializing scan...")

        # 2. Instantiate the logic engine with callbacks 
        # This allows the logic to 'talk' to the UI without being 'part' of it
        self.core = AstroScannerCore( # Store reference
            log_callback=self.log,
            progress_callback=self.update_progress
        )

        try:
            # --- Capture Start Time ---
            start_time = time.time()

            # 3. Execute logic
            data = self.core.scan_folder(self.selected_path)

            # --- Calculate Duration ---
            end_time = time.time()
            duration = end_time - start_time

            if self.core.stop_requested:
                self.log("Scan was stopped by the user.")
                self.after(0, lambda: messagebox.showinfo("Scan Stopped", "The scan was stopped. Partial results may not be saved."))
                return

            if not data:
                self.after(0, lambda: messagebox.showwarning("No Data", "No compatible files were found."))
                return

            # 4. Save results        
            output_file = os.path.join(os.getcwd(), "astro_inventory.csv")
            self.core.save_to_csv(data, output_file)
            
            # 5. Notify UI of completion
            self.log(f"SUCCESS: {len(data)} files indexed in {duration:.2f} seconds.")
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