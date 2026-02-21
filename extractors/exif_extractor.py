from extractors.fits_extractor import FITS_AVAILABLE

from .base import BaseExtractor

try:
    import exifread
    EXIF_AVAILABLE = True
except ImportError:
    exifread = None
    EXIF_AVAILABLE = False

# Force PyInstaller to include exifread
if False:
    import exifread

class ExifExtractor(BaseExtractor):
    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda x: None)
        with open('debug.log', 'a') as f:
            f.write(f"EXIF_AVAILABLE: {EXIF_AVAILABLE}\n")

    def extract(self, path):
        """EXIF strategy: returns a dict of metadata."""
        if not EXIF_AVAILABLE:
            return {}
        try:
            with open(str(path), 'rb') as f:
                tags = exifread.process_file(f)
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
