import os
import sys

project_root = os.path.abspath(os.getcwd())
original_path = list(sys.path)

# Prevent the local ./alembic migrations directory from shadowing
# the installed Alembic package during this import.
sys.path = [
    p for p in sys.path
    if p and os.path.abspath(p) != project_root
]

from alembic.config import main as alembic_main

# Restore project imports for env.py / app imports used by migrations.
sys.path = original_path

alembic_main(argv=["upgrade", "head"])
