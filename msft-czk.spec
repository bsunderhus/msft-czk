# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for msft-czk.
#
# Build: pyinstaller msft-czk.spec
# Output: dist/msft-czk  (single self-contained binary, no Python runtime required)
#
# Hidden imports cover pdfminer sub-packages loaded dynamically by pdfplumber.
# If a ModuleNotFoundError appears at runtime, add the missing module here.

from PyInstaller.utils.hooks import collect_all
import glob, os, sys

charset_datas, charset_binaries, charset_hiddenimports = collect_all("charset_normalizer")

# charset_normalizer ships a mypyc-compiled extension at site-packages root
# (e.g. 81d243bd2c585b0f4821__mypyc.cpython-312-x86_64-linux-gnu.so).
# collect_all() misses it because it lives outside the package directory.
_sp = next(iter(glob.glob(os.path.join(sys.prefix, "lib", "python*", "site-packages"))), "")
_mypyc_so = glob.glob(os.path.join(_sp, "*__mypyc*.so"))
_extra_binaries = [(so, ".") for so in _mypyc_so]

a = Analysis(
    ["src/msft_czk/cli.py"],
    pathex=[],
    binaries=charset_binaries + _extra_binaries,
    datas=charset_datas,
    hiddenimports=charset_hiddenimports + [
        "pdfminer.high_level",
        "pdfminer.layout",
        "pdfminer.pdfpage",
        "pdfminer.pdfinterp",
        "pdfminer.converter",
        "pdfminer.pdfdocument",
        "pdfminer.pdfparser",
        "pdfminer.utils",
    ],
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
    a.binaries,
    a.datas,
    [],
    name="msft-czk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
