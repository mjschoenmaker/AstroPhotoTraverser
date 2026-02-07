import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- THE FIX FOR FOLDER IMPORTS ---
# This adds the parent directory to the system path so it can find your scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from astrophoto_traverser import AstroScannerCore
import config

@pytest.fixture
def scanner():
    # Initialize scanner with dummy callbacks to avoid console output during tests
    return AstroScannerCore(log_callback=lambda x: None, progress_callback=lambda x, y: None)

def test_scan_folder_finds_supported_extensions(scanner, tmp_path):
    # Arrange: Create a fake directory structure
    subdir = tmp_path / "subfolder"
    subdir.mkdir()
    (tmp_path / "light.fits").write_text("fake data")
    (subdir / "dark.cr2").write_text("fake data")
    (tmp_path / "notes.txt").write_text("should be ignored")

    # Act
    # We mock the internal metadata extraction so it doesn't try to actually read the "fake data"
    with patch.object(AstroScannerCore, '_extract_metadata', return_value={'Status': 'Mocked'}):
        results = scanner.scan_folder(tmp_path)

    # Assert
    assert len(results) == 2
    filenames = [r['Filename'] for r in results]
    assert "light.fits" in filenames
    assert "dark.cr2" in filenames
    assert "notes.txt" not in filenames

@patch('config.fits.open')
def test_fits_metadata_extraction(mock_fits_open, scanner, tmp_path):
    # Arrange: Mock the FITS header structure
    mock_header = {
        'EXPTIME': 180,
        'GAIN': 100,
        'INSTRUME': 'ZWO ASI294MC Pro',
        'FILTER': 'L-Extreme'
    }
    # Mocking the context manager fits.open()
    mock_hdulist = MagicMock()
    mock_hdulist.__enter__.return_value = [MagicMock(header=mock_header)]
    mock_fits_open.return_value = mock_hdulist

    # Create a dummy file path
    fake_file = tmp_path / "test.fits"
    fake_file.write_text("dummy")

    # Act
    # Manually calling the logic that handles FITS files (assuming you refactor it into a method)
    # In your current script, this logic is inside the loop, so we mock the loop's dependency
    results = scanner.scan_folder(tmp_path)

    # Assert
    assert results[0]['Exposure'] == 180
    assert results[0]['Gain'] == 100
    assert results[0]['Filter'] == 'L-Extreme'