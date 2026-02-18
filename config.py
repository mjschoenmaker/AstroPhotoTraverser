import re
try:
    import astropy.io.fits as fits
    FITS_AVAILABLE = True
except ImportError:
    fits = None
    FITS_AVAILABLE = False

try:
    import exifread
    EXIF_AVAILABLE = True
except ImportError:
    exifread = None
    EXIF_AVAILABLE = False

# Force PyInstaller to include astropy and exifread
if False:
    import astropy.io.fits
    import exifread

# --- FILE TYPE CONFIGURATION ---
# Map file extensions to their respective metadata extraction methods    
FILE_TYPES = {
    '.fit': 'fits',
    '.fits': 'fits',
    '.cr2': 'exif',
    '.dng': 'exif',
    '.jpg': 'exif',
    '.jpeg': 'exif'
}

# --- GLOBAL CONFIGURATION ---
FILTER_KEYWORDS = {
    'lxtrme': 'L-eXtreme',
    'lxtreme': 'L-eXtreme',
    'lextreme': 'L-eXtreme',
    'l-extreme': 'L-eXtreme',
    'lenhance': 'L-eNhance',
    'l-enhance': 'L-eNhance',
    'lultimate': 'L-Ultimate',
    'l-ultimate': 'L-Ultimate',
    'l-pro': 'L-Pro',
    'lpro': 'L-Pro',
    'uvir': 'UV/IR Cut',
    'uv/ir': 'UV/IR Cut',
    'irblock': 'UV/IR Cut',
    'irblocked': 'UV/IR Cut',
    'ir-block': 'UV/IR Cut',
    'ir filter': 'UV/IR Cut',
    'halpha': 'Ha',
    'ha': 'Ha',
    'h': 'Ha',
    'oxygen': 'OIII',
    'oiii': 'OIII',
    'o3': 'OIII',
    'o': 'OIII',
    'sulphur': 'SII',
    'sulfur': 'SII',
    'sii': 'SII',
    's2': 'SII',
    's': 'SII',
    'r': 'Red',
    'g': 'Green',
    'b': 'Blue',
    'l': 'Luminance',
    'cls': 'CLS'
}

FILE_REGEX = re.compile(
    r'_(?P<exposure>[\d.]+)s'                # 180.0s
    r'_Bin(?P<bin>\d+)'                 # Bin1
    r'_(?P<camera>[^_]+)'               # 294MC
    r'(?:_(?P<filter>[^_]+))?'          # optional filter
    r'_gain(?P<gain>\d+)'               # gain120
    r'_(?P<timestamp>\d{8}-\d{6})'      # 20250405-214232
    r'_(?P<temperature>-?[\d]+(?:\.[\d]+)?)C'  # -10C or -10.5C
    r'_(?P<rotation>\d+)deg'            # 90deg
)

# Matches folder names starting with YYYYMMDD or YYYY-MM-DD (also allows underscores)
DATE_FOLDER_RE = re.compile(r'^\d{4}[-_]?\d{2}[-_]?\d{2}')

CALIBRATION_KEYWORDS = ['darks', 'bias', 'flats', 'calibration']

def identify_filter(folder_name):
    for key, formal_name in FILTER_KEYWORDS.items():
        if re.search(r'\b' + re.escape(key) + r'\b', folder_name, re.IGNORECASE):
            return formal_name
    return "Broadband/Unknown"

