"""Punto de entrada. Uso: python main.py"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from channels.consola import ejecutar_repl  # noqa: E402

if __name__ == "__main__":
    ejecutar_repl()
