"""Startup script: rebuild site.db from all import layers, then start uvicorn."""

import os
import sqlite3
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"STDERR from {label}:\n{result.stderr}")
    if result.returncode != 0:
        print(f"WARNING: {label} exited with code {result.returncode}, continuing...")

# --- Log source layer counts ---
DB_PATH = Path("site.db")
if DB_PATH.exists():
    print("\n=== Source layer counts ===")
    db = sqlite3.connect(str(DB_PATH))
    for row in db.execute("SELECT source, COUNT(*) FROM records GROUP BY source ORDER BY source"):
        print(f"  {row[0]}: {row[1]}")
    total = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    print(f"  TOTAL: {total}")
    db.close()

# --- Start uvicorn ---
port = int(os.environ.get("PORT", 3000))
print(f"\nStarting uvicorn on port {port}...")
import uvicorn
uvicorn.run("atlas.app:app", host="0.0.0.0", port=port)
