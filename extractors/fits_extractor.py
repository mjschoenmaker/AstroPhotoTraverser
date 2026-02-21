from pathlib import Path
from .base import BaseExtractor
from pathlib import Path

try:
    import astropy.io.fits as fits
    FITS_AVAILABLE = True
except ImportError:
    fits = None
    FITS_AVAILABLE = False

# Force PyInstaller to include astropy
if False:
    import astropy.io.fits

class FitsExtractor(BaseExtractor):
    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda x: None)
        with open('debug.log', 'a') as f:
            f.write(f"FITS_AVAILABLE: {FITS_AVAILABLE}\n")

    def extract(self, path):
        """FITS strategy: returns a dict of metadata."""
        if not FITS_AVAILABLE:
            return {}
        try:
            with fits.open(str(path), mode='readonly') as hdul:
                header = hdul[0].header # type: ignore
                # Return keys that match our dataclass fields

                return {
                    'camera': header.get('INSTRUME') or header.get('CAMERA'),
                    'gain': str(header.get('GAIN', '') or header.get('ISO', '')),
                    'temperature': str(header.get('CCD-TEMP') or header.get('SET-TEMP', '')),
                    'exposure': str(header.get('EXPTIME', '')),
                    'filter': header.get('FILTER')
                }
        except Exception as e:
            with open('debug.log', 'a') as f:
                f.write(f"Error reading FITS header for {path}: {e}\n") 
                self.log(f"Error reading FITS header for {path}: {e}")
            return {}
