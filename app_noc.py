"""Entrada do aplicativo e da verificação do executável Windows."""

import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verificar-build":
        from scripts.verificar_build import verificar

        raise SystemExit(verificar(Path(sys.argv[2])))
    else:
        from noc.interface import main

        main()
