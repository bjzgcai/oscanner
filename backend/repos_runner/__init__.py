"""
Repository Runner Package
"""

import sys
from pathlib import Path

# Add backend directory to Python path to allow 'repos_runner' imports
# This must be done before any other imports that use 'repos_runner' as a top-level package
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
