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


>Here is your detailed shooting advice for both setups:
>
>**1. The High-Resolution Choice: EdgeHD 9.25 at f/7 (~1645mm)**
>
>Your inventory shows you have plenty of wide-field data on the "classics," but several prime high-resolution targets are missing from your EdgeHD logs.
>
>* **Target: M81 (Bode’s Galaxy)**
>
>   * **Why:** Surprisingly, your logs show zero high-resolution data for M81 with the EdgeHD (you only have wide-field and C8 data). This is the perfect time of year for it as it sits high in Ursa Major.
>
>   * **Goal:** Capture the intricate spiral arm details and the "Holmberg IX" dwarf galaxy nearby.
>
>   * **Filters:** Broadband (Luminance + RGB). If you have time, 1-2 hours of Ha can help pop the HII regions in the arms.
>
>**2. The Wide-Field Choice: William Optics GT81 at 385mm**
>
>At this focal length, you should focus on targets that are too large for the EdgeHD or require massive integration time to reveal faint structures.
>
>* **Target: Sh2-240 (The Spaghetti Nebula)**
>
>   * **Why:** You currently have only 4.3 hours of Ha data on this object. The Spaghetti Nebula is a massive (~3-degree) supernova remnant that fits your 385mm FOV perfectly but is notoriously faint. It is currently well-placed in Auriga.
>
>   * **Goal:** You need at least 15–20 hours total to make this "pop." Tonight is a great night to add a 6-hour block of OIII or more Ha.
>
>   * **Filters:** Narrowband (Ha and OIII).

<img width="978" height="716" alt="image" src="https://github.com/user-attachments/assets/3cf8df64-8f3f-4b59-981f-7c40c9afb7f9" />


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
In case certain files are found on telescope or session level, that can be identified as edits, the resulting CSV will flag it allowing for discovery of those targets that have unprocessed data sitting on your harddrive. Perfect material for a lazy [**Stacking Sunday**](https://www.youtube.com/playlist?list=PL40pZwFiEpXPCwSy82MzCJp1QVy7tSKNx).

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
