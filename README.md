# AstroPhotoTraverser 🌌

**AstroPhotoTraverser** is a Python-based desktop utility designed to scan massive directories of astrophotography images (FITS, RAW, and common formats) and consolidate their metadata into a single, clean CSV inventory.

Whether you are organizing years of data or preparing files for a stacking project, this tool eliminates the manual work of checking headers for Gain, Exposure, Temperature, and Filters.

## ✨ Features

* **Multi-Format Support**: Handles `.fits`, `.fit`, `.cr2` (Canon RAW), `.dng`, `.jpg`, and `.png`.
* **Smart Regex Parsing**: Gets metadata from parsing file names and folder names (e.g., `_180s_Gain100_...`).
* **FITS**: If missing meta data still, it will pull it directly from FITS headers (EXPOSURE, GAIN, SET-TEMP, FILTER, etc.).
* **DSLR/RAW**: Or EXIF data for camera models that don't save in FITS format.
* **Portable Output**: Generates a standard `astro_inventory.csv` which you can import into Excel, Google Sheets etc, for further analysis.

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* Dependencies: `customtkinter`, `astropy`, `exifread`

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mjschoenmaker/AstroPhotoTraverser.git
cd AstroPhotoTraverser

```


2. Install requirements:
```bash
pip install -r requirements.txt

```



### Running the App

```bash
python astrophoto-traverser.py

```

## 🛠️ Build as Executable
There is a Windows executable available in [releases](https://github.com/mjschoenmaker/AstroPhotoTraverser/releases) 

To create a standalone `.exe` for Windows using PyInstaller:

```bash
pyinstaller --clean astrophoto-traverser.spec

```

The output will be located in the `dist/` folder.

## 📁 Project Structure

* `astrophoto-traverser.py`: Main entry point and CustomTkinter UI.
* `config.py`: Configuration for regex patterns and filter keyword mapping.
* `astrophoto-traverser.spec`: PyInstaller configuration for bundling assets like `customtkinter` and `astropy`.

## 🤝 Contributing

Contributions are welcome! If you have a specific FITS header format or a new camera type that isn't being parsed correctly, please open an issue or submit a pull request.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Clear Skies!** 🔭
