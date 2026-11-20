"""Versão única compartilhada pelo aplicativo e pelos artefatos distribuídos."""

import sys
from pathlib import Path

__version__ = (Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "VERSION").read_text(encoding="utf-8").strip()
