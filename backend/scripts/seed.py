import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "calendar_backend.settings")

import django

django.setup()

from scripts.domain_seed import seed

if __name__ == "__main__":
    seed()
