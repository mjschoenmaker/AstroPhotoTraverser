# AstroPhotoTraverser 🌌

**AstroPhotoTraverser** is a Python-based desktop utility designed to scan massive directories of astrophotography images (FITS, RAW, and common formats) and consolidate their metadata into a single, clean CSV inventory.

Whether you are organizing years of data or preparing files for a stacking project, this tool eliminates the manual work of checking headers for Gain, Exposure, Temperature, and Filters.

## ✨ Features

* **Multi-Format Support**: Handles `.fits`, `.fit`, `.cr2` (Canon RAW), `.dng`, `.jpg`, and `.png`.
* **Smart Regex Parsing**: Gets metadata from parsing file names and folder names (e.g., `_180s_Gain100_...`).
* **FITS**: If missing meta data still, it will pull it directly from FITS headers (EXPOSURE, GAIN, SET-TEMP, FILTER, etc.).
* **DSLR/RAW**: Or EXIF data for camera models that don't save in FITS format.
* **Portable Output**: Generates a standard `astro_inventory.csv` which you can import into Excel, Google Sheets etc, for further analysis.

## 🤖 Examples of use
* Run statistics on your entire collection
* Find out which object is your favorite
* Or which telescope you've used the most
* Be able to calculate the total amount of integration
* Leverage AI tools on your dataset

    One nice usage I got was just uploading the resulting CSV to Gemini and prompt it for detailed advise what to shoot that night from my location, with this as a result:

| Time | Target (EdgeHD 925) | Target (GT81) | Notes |
| :--- | :--- | :--- | :--- |
| **19:30 - 23:00** | M82 / M81 (High in North) | Sh2-240 (High in West) | Best time for the Spaghetti Nebula before it sinks. |
| **23:00 - 04:30** | NGC 4565 (Approaching Zenith) | Markarian's Chain (Rising in East) | Peak "Galaxy Season" conditions. |
| **04:30+** | Pack up | Pack up | Moon rises / Dawn approaches. |

## 🚀 Getting Started

### Prerequisites

* Python 3.10+
* Dependencies: `customtkinter`, `astropy`, `exifread`

### File structure
This project originates from how I personally store my astrophotography data. I detailed the structure in this YouTube video [**Astrophotography File Management - How to organize your files**](https://www.youtube.com/watch?v=Io6awemQF88)

```
    Root
    |-- Object Name
        |-- Focal Length Telescope
            |-- YYYY-MM-DD Location with filter (if known)
                |-- subs            
```
In case certain files are found on telescope or session level, that can be identified as edits, the resulting CSV will flag it

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
* `extractors`: A folder with the extractor method for common file types.

## 🤝 Contributing

Contributions are welcome, but bear in mind that this tool is (for now at least) tightly coupled to the way I store my 
Astrophotography collection.

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Clear Skies!** 🔭
