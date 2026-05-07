"""Startup wrapper with debug logging for Railway deployment."""

import os
import sys
from pathlib import Path

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"Files in CWD: {os.listdir('.')}")
print(f"Files in atlas/: {os.listdir('atlas') if Path('atlas').exists() else 'atlas/ not found'}")

# Check site.db
site_db = Path("site.db")
print(f"site.db exists: {site_db.exists()}")
if site_db.exists():
    print(f"site.db size: {site_db.stat().st_size} bytes")

# Try importing atlas.db to check DB_PATH resolution
try:
    from atlas.db import DB_PATH
    print(f"DB_PATH from atlas.db: {DB_PATH}")
    print(f"DB_PATH exists: {DB_PATH.exists()}")
    if DB_PATH.exists():
        print(f"DB_PATH size: {DB_PATH.stat().st_size} bytes")
except Exception as e:
    print(f"Error importing atlas.db: {e}")

# Try importing the app
try:
    from atlas.app import app
    print("Successfully imported atlas.app")
except Exception as e:
    print(f"Error importing atlas.app: {e}")
    sys.exit(1)

# Start uvicorn
port = int(os.environ.get("PORT", 3000))
print(f"Starting uvicorn on port {port}...")
import uvicorn
uvicorn.run("atlas.app:app", host="0.0.0.0", port=port)
