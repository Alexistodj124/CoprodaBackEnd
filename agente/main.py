"""Punto de entrada. Uso: python main.py [whatsapp]"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

if __name__ == "__main__":
    if sys.argv[1:] == ["whatsapp"]:
        from channels.whatsapp import ejecutar_servidor

        ejecutar_servidor()
    else:
        from channels.consola import ejecutar_repl

        ejecutar_repl()
