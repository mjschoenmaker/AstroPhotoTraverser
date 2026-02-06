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
    
# --- GLOBAL CONFIGURATION ---
FILTER_KEYWORDS = {
    'lextreme': 'L-Extreme',
    'l-pro': 'L-Pro',
    'lpro': 'L-Pro',
    'uvir': 'UV/IR Cut',
    'uv/ir': 'UV/IR Cut',
    'ha': 'Ha',
    'h': 'Ha',
    'oiii': 'OIII',
    'o3': 'OIII',
    'o': 'OIII',
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
    r'_(?P<exp>[\d.]+)s'                # 180.0s
    r'_Bin(?P<bin>\d+)'                 # Bin1
    r'_(?P<camera>[^_]+)'               # 294MC
    r'(?:_(?P<filter>[^_]+))?'          # optional filter
    r'_gain(?P<gain>\d+)'               # gain120
    r'_(?P<timestamp>\d{8}-\d{6})'      # 20250405-214232
    r'_(?P<temp>-?[\d]+(?:\.[\d]+)?)C'  # -10C or -10.5C
    r'_(?P<rotation>\d+)deg'            # 90deg
)

# Matches folder names starting with YYYYMMDD or YYYY-MM-DD (also allows underscores)
DATE_FOLDER_RE = re.compile(r'^\d{4}[-_]?\d{2}[-_]?\d{2}')

def identify_filter(folder_name):
    folder_lower = folder_name.lower()
    for key, formal_name in FILTER_KEYWORDS.items():
        if re.search(r'\b' + re.escape(key) + r'\b', folder_lower):
            return formal_name
    return "Broadband/Unknown"

