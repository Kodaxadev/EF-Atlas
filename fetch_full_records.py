#!/usr/bin/env python3
import requests
import json

base = "http://127.0.0.1:8000"

ids = [
    "02bf1c5f4792ed87d55a077d06c78780e452804a14b629f4c8152c6e8d29a44d",
    "0cd9162c13f0ae03186885f028a2c3d8c774869bfb0f6af5f450b1446a88a6a1",
    "10457946ad5b2f4357dc150b70e575fe20170d8be5b7815b5f629eff7a96561d",
    "12342dfb485d08e523dc4c9d098e648b3193c6fed9628d1b56bb953570891098",
    "14cf1aa30a1a4a0baffcd30bebaf0f499304741601bb7dde4d8d0d16da6c853e",
    "2e8138ad08ab87b2e8e727aa272e0c863554a28bf1d1823acccabdc672b20632",
    "35706531d1851fb8d29974576b7d459fda91f3878cfbe434d9aa1074af5ffed0",
    "3a6fa7308d04d3b395e9b1bc2b2166e24237e7578b01ea2848df87a131473f18",
    "478ee6fcd19f0418e0e90be2b253e0bb66e6977a8fb32cedee915f6e320c3d21",
    "5a9edcf0c56865c96d819b6873cd288ec3f117ca5171c391042d5173814608ff"
]

data = {}
for rid in ids:
    r = requests.get(f"{base}/api/records/{rid}")
    if r.status_code != 200:
        print(f"FAIL: {rid} returned {r.status_code}")
        continue
    d = r.json()
    data[rid] = {
        "title": d["title"],
        "url": d["url"],
        "authority_tier": d["authority_tier"],
        "text": d["text"][:1000]
    }

print(json.dumps(data, indent=2))
