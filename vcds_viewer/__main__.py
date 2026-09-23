"""Uruchamianie: python -m vcds_viewer [plik.csv ...]"""

from __future__ import annotations

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
