"""Startup script: rebuild site.db from all import layers, then start uvicorn."""

import os
import subprocess
import sys
from pathlib import Path

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")

# --- Import pipeline (runs on every startup to ensure all layers are present) ---
IMPORT_STEPS = [
    ("Corpus + game files", [sys.executable, "ef_import_site_db.py", "--all"]),
    ("Scetrov notes", [sys.executable, "ef_import_scetrov_notes.py"]),
    ("EVE Datacore", [sys.executable, "ef_import_eve_datacore.py"]),
    ("World API", [sys.executable, "ef_import_world_api.py"]),
    ("Watch notes", [sys.executable, "ef_import_watch_notes.py"]),
]

for label, cmd in IMPORT_STEPS:
    print(f"\n--- Running: {label} ---")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"WARNING: {label} exited with code {result.returncode}, continuing...")

# --- Start uvicorn ---
port = int(os.environ.get("PORT", 3000))
print(f"\nStarting uvicorn on port {port}...")
import uvicorn
uvicorn.run("atlas.app:app", host="0.0.0.0", port=port)
