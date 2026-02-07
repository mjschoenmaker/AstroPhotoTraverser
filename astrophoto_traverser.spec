# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter
from PyInstaller.utils.hooks import collect_data_files

# Get the path to the customtkinter library
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['astrophoto_traverser.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter/')  # Correctly include customtkinter UI files
    ],
    hiddenimports=[
        'astropy', 
        'astropy.io.fits', 
        'exifread',
        'config'
    ],
    collect_submodules=[],  
    collect_all=['exifread'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[], 
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='astrophoto_traverser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='astrophoto_traverser',
)