from pathlib import Path


backend_dir = Path(SPECPATH)

a = Analysis(
    [str(backend_dir / "scripts" / "backend_sidecar.py")],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[(str(backend_dir / "config"), "config")],
    hiddenimports=[
        "uvicorn.lifespan.on",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["playwright"],
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
    name="jlu-notice-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
