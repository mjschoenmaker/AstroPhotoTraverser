import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the parent directory is in the path to find astrophoto_traverser and config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrophoto_traverser import AstroScannerCore
import config

@pytest.fixture
def scanner():
    # Initialize scanner with dummy callbacks
    return AstroScannerCore(log_callback=lambda x: None, progress_callback=lambda x, y: None)

def test_filename_regex_parsing(scanner, tmp_path):
    """
    Tests if the FILE_REGEX in config.py correctly identifies components
    from a standard filename: Light_Orion_180.0s_Bin1_294MC_L-Extreme_gain120_20250405-214232_-10C_90deg_001.fit
    """
    test_filename = "Light_Orion_180.0s_Bin1_294MC_L-Extreme_gain120_20250405-214232_-10C_90deg_001.fit"
    match = config.FILE_REGEX.search(test_filename)
    
    assert match is not None
    assert match.group('exposure') == "180.0"
    assert match.group('bin') == "1"
    assert match.group('camera') == "294MC"
    assert match.group('filter') == "L-Extreme"
    assert match.group('gain') == "120"
    assert match.group('timestamp') == "20250405-214232"
    assert match.group('temperature') == "-10"
    assert match.group('rotation') == "90"

def test_folder_structure_regex(scanner, tmp_path):
    """
    Tests if the FOLDER_REGEX in config.py correctly identifies session dates
    and object names from folder paths.
    """
    # Simulate a path
    test_path = "2024-01-01 Backyard/"
    match = config.DATE_FOLDER_RE.search(test_path)
    
    assert match is not None # there is a date folder

def test_get_metadata_from_path(scanner, tmp_path):
    """
    Tests if the get_metadata_from_path method correctly extracts metadata from a given path.
    """
    # Simulate a path
    test_path = Path("M42/2000mm Telescope/2024-02-07 Backyard UVIR/Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_gain456_001.fits")
    
    obj_name, telescope, session_info = scanner._get_metadata_from_path(test_path, "")
    
    assert obj_name == "M42"
    assert telescope == "2000mm Telescope"
    assert session_info == "2024-02-07 Backyard UVIR"

def test_filter_in_session(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard UVIR" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "No"

def test_filter_in_filename(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "No"

def test_ignore_filter_in_session(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard L-Extreme" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "No"

def test_missing_telescope(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M105 - triplet in Leo" / "2024-02-07 Backyard UVIR" / "Light_M105_123deg_67.0s_-273C_Bin1_PlayerOne_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "missing info"
    assert result['Object'] == "M105 - triplet in Leo"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "No"

def test_folder_with_tif_edits_in_session(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits in the same session
    path2 = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "This is a nice edit.tif"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake tif data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_tif_edits_in_session_subfolders(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits in the same session
    path2 = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "subfolder" / "sub-subfolder" / "This is a nice edit.tif"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake tif data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_tif_edits_for_telescope(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits on the telescope level
    path2 = tmp_path / "M42" / "2000mm Telescope" /  "This is a nice edit.tif"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake tif data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_psd_edits_in_session(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits in the same session
    path2 = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "This is a nice edit.psd"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake psd data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_psd_edits_for_telescope(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits on the telescope level
    path2 = tmp_path / "M42" / "2000mm Telescope" / "This is a nice edit.psd"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake psd data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_stack_edits_in_session(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits in the same session
    path2 = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "This is a nice stacked result.fit"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake file data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"

def test_folder_with_stack_edits_for_telescope(scanner, tmp_path):
    # Create a real folder structure
    path = tmp_path / "M42" / "2000mm Telescope" / "2024-02-07 Backyard" / "Light_M42_123deg_67.0s_-273C_Bin1_PlayerOne_UVIR_gain456_001.fits"
    path.parent.mkdir(parents=True)
    path.write_text("fake fits data") # create a dummy file

    # another file that simulates edits on the telescope level
    path2 = tmp_path / "M42" / "2000mm Telescope" / "This is a nice stacked result.fit"
    path2.parent.mkdir(parents=True, exist_ok=True)
    path2.write_text("fake file data") # create a dummy file

    # Call the scan_folder method
    results = scanner.scan_folder(str(tmp_path))

    # Assert the logic inside the method works
    assert len(results) == 1
    result = results[0]
    assert result['Telescope'] == "2000mm Telescope"
    assert result['Object'] == "M42"
    assert result['Exposure'] == "67.0"
    assert result['Bin'] == "1"
    assert result['Camera'] == "PlayerOne"
    assert result['Filter'] == "UV/IR Cut"
    assert result['Gain'] == "456" 
    assert result['Temp'] == "-273"
    assert result['Rotation'] == "123"
    assert result['Edits Detected'] == "Yes"
