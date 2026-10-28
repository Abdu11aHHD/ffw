"""Application package and Windows native-library search path setup."""
import os
import sys
from pathlib import Path

# Python 3.8+ does not search PATH for extension dependencies. The optional
# msvc-runtime wheel installs the redistributable DLLs inside the virtualenv.
_dll_handles = []
if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    for _path in (Path(sys.prefix), Path(sys.prefix) / "Scripts"):
        if _path.is_dir():
            _dll_handles.append(os.add_dll_directory(str(_path)))
