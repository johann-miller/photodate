# photodate.spec
import sys
import os
from PyInstaller.building.api import PYZ, EXE, COLLECT
from PyInstaller.building.build_main import Analysis

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('fonts', 'fonts')] if os.path.isdir('fonts') else [],
    hiddenimports=[],
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
    name='photodate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,      # UPX disabled — avoids antivirus false positives on Windows
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,      # set to 'assets/icon.ico' (Win) or 'assets/icon.icns' (macOS) if you add one
)

# macOS .app bundle — ignored on Windows/Linux
if sys.platform == 'darwin':
    from PyInstaller.building.osx import BUNDLE
    app = BUNDLE(
        exe,
        name='Photodate.app',
        icon=None,
        bundle_identifier='com.yourname.photodate',
    )
