"""Use existing Windows 8.3 aliases to keep GCC process arguments below limits."""
import ctypes
import os
from pathlib import Path
import sys

path=str(Path(sys.argv[1]).absolute())
if os.name=="nt":
    buffer=ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(path,buffer,len(buffer)):
        path=buffer.value
print(path)
