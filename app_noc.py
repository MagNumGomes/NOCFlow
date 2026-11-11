"""Entrada do aplicativo e da verificação do executável Windows."""

from pathlib import Path
import sys


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verificar-build":
        from verificar_build import verificar

        raise SystemExit(verificar(Path(sys.argv[2])))
    else:
        from noc.interface import main

        main()
