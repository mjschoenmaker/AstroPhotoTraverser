import os
import csv
import re

from pathlib import Path
from models import SessionMetadata
from dataclasses import fields

import config

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

    def scan_folder(self, root_path):
        root = Path(root_path)
        valid_extensions = config.FILE_TYPES.keys()
        
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

    def save_to_csv(self, data_rows, output_path):
        """Handles the file IO for CSV generation."""
        if not data_rows:
            return
        keys = data_rows[0].keys()
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_rows)

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

    def _needs_header_extraction(self, ext, meta):
        """
        Returns True if critical metadata is missing. 
        As configured in config.REQUIRED_METADATA_FIELDS.
        """
        extraction_type = config.FILE_TYPES.get(ext)
        required_fields = config.REQUIRED_METADATA_FIELDS.get(extraction_type, []) # type: ignore
        return any(not meta.get(field) for field in required_fields)

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
        # 1. Look for edit-related file extensions or "stack" in the filename
        for f in files:
            f_lower = f.lower()
            if any(f_lower.endswith(ext) for ext in config.EDIT_INDICATORS) or "stack" in f_lower:
                
                # 2. Exclude calibration folders (darks, bias, flats) from triggering an 'Edit' flag
                if not any(k in current_dir.lower() for k in config.CALIBRATION_KEYWORDS):
                    return True
                    
        return False

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

    def _get_metadata_from_filename(self, file_name):
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

    def _cleanup_parsed_metadata(self, meta, file_name, session_info):
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
                meta['filter'] = meta['camera']
            meta['camera'] = None

        # 3. Attempt to find filter in the filename if still missing
        if not meta.get('filter'):
            for key, formal_name in config.FILTER_KEYWORDS.items():
                # Look for filter keywords delimited by underscores or dashes
                if re.search(r'[_\-]' + re.escape(key) + r'[_\-]', file_name, re.IGNORECASE):
                    meta['filter'] = formal_name
                    break

        # 4. If filter is still missing, attempt to identify it from the session folder name as a last resort, since it's likely consistent for the session
        if not meta.get('filter') or meta['filter'] in [None, 'Broadband/Unknown']:
            meta['filter'] = config.identify_filter(session_info)

        # Whatever the case, make sure that filter is set to a known value (either identified or "Broadband/Unknown")
        if (meta.get('filter') and meta['filter'] not in config.FILTER_KEYWORDS.values()):
            meta['filter'] = config.identify_filter(meta.get('filter'))

        # If gain is a non numeric string, invalidate it
        gain = meta.get('gain') 
        if gain and not re.match(r'^\d+$', str(gain)):
            meta['gain'] = None

        return meta

    def _is_valid_file(self, path, session_info):
        file_name = path.name
        # Only include files whose immediate parent folder starts with a date (YYYYMMDD or YYYY-MM-DD)
        parent_name = (session_info or '').strip()
        if not config.DATE_FOLDER_RE.match(parent_name):
            # self.log(f"Skipping file not in date folder: {file_name} (parent='{session_info}')")
            return False

        # Only include image files that start with "Preview_", "Light_", "CRW_", or "IMG_" and don't end with "_thn.jpg"
        if not file_name.startswith(config.ALLOWED_FILE_PREFIXES) or file_name.endswith(config.SKIPPED_FILE_SUFFIXES):
            # self.log(f"Skipping file: {file_name} (parent='{session_info}')")
            return False
        
        # Skip files that reside in a folder that indicate calibration frames (e.g., "darks", "bias", "flats")
        lower_path_str = str(path).lower()
        if any(keyword in lower_path_str for keyword in config.CALIBRATION_KEYWORDS):
            # self.log(f"Skipping calibration file: {file_name} (parent='{session_info}')")
            return False
        
        return True

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
        meta = self._get_metadata_from_filename(file_name)

        # Cleanup and cross-validate the parsed metadata to correct common misplacements (e.g., camera vs. filter)
        meta = self._cleanup_parsed_metadata(meta, file_name, session_info)

        # This pulls values (like camera or filter) already found in previous files.
        self._sync_session_data(meta, session)

        # 4. Conditional Extraction (The "Gatekeeper")
        ext = path.suffix.lower()
        extractor_func = self._extractors.get(ext)
        
        # Check if we are still missing critical info after syncing with session
        if extractor_func and self._needs_header_extraction(ext, meta):
            # Get the metadata from the appropriate extractor
            extracted_meta = extractor_func(path)
            
            # Cleanup and cross-validate the extracted metadata as well, since FITS headers can be messy and inconsistent
            extracted_meta = self._cleanup_parsed_metadata(extracted_meta, file_name, session_info)

            # Sync the new findings back to the session cache for the next files
            self._sync_session_data(extracted_meta, session)
            
            # Update meta with any new info found from the file header
            meta.update({k: v for k, v in extracted_meta.items() if v})

        # 5. Syncing metadata with session cache to fill in missing values and ensure consistency
        self._sync_session_data(meta, session)

        # 6. If still missing major metadata, log a skipped-file note
        if not meta:
            self.log(f"Note: filename did not match expected patterns: {file_name}")
            return

        # 7. Formatting the result
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