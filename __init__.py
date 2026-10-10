import os
import sys

_flood_dir = os.path.dirname(__file__)
if _flood_dir not in sys.path:
    sys.path.insert(0, _flood_dir)
