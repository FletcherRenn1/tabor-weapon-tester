# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('assets/tesseract/tesseract.exe', 'assets/tesseract'),
        *[
            (dll, 'assets/tesseract')
            for dll in __import__('glob').glob('assets/tesseract/*.dll')
        ],
    ],
    datas=[
        ('assets/fonts/AlteinxSans.otf', 'assets/fonts'),
        ('assets/tesseract/tessdata/eng.traineddata', 'assets/tesseract/tessdata'),
        ('assets/ui/check.svg', 'assets/ui'),
        ('VERSION', '.'),
    ],
    hiddenimports=[
        'pytesseract',
        'pyttsx3',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'mss',
        'cv2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='tabor-weapon-tester',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
