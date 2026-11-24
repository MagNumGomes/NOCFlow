# Build Windows em pasta: interface, ponte local e extensão do Edge.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

raiz = Path(SPECPATH).parent
dados = copy_metadata("google-genai", recursive=True)
dados += copy_metadata("groq", recursive=True)
dados += copy_metadata("winrt-runtime")
dados += collect_data_files("tzdata")
dados += [(str(raiz / ".env.example"), ".")]
dados += [(str(raiz / "VERSION"), ".")]
dados += [(str(raiz / "edge_extension"), "edge_extension")]

analise = Analysis(
    [str(raiz / "app_noc.py")],
    pathex=[str(raiz)],
    binaries=collect_dynamic_libs("winrt"),
    datas=dados,
    # noc.ui/domain/services/infra usam imports estáticos, descobertos por Analysis.
    hiddenimports=collect_submodules("google.genai", filter=lambda nome: ".tests" not in nome and "._test" not in nome) + collect_submodules("groq") + collect_submodules("winrt"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["playwright", "pypdf", "ruff", "tests"],
    noarchive=False,
)
pyz = PYZ(analise.pure)
exe = EXE(
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="NOCFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coleta = COLLECT(
    exe,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    name="NOCFlow",
)
