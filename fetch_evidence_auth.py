#!/usr/bin/env python3
import requests
import json

base = "http://127.0.0.1:8000"

# Priority records for smart-gate extension authorization
priority_ids = [
    "d7289d6b29f7c09c315aa4658894804af67b33cde7024dfff296526f128a46cf",  # gate.move
    "30d14f639ad4d269ba8f7e30c846d05e832122ee8f1cc538c32f0e9a30d0c352",  # authorise-gate.ts
    "9c7a59eb6e01942bbdf0e118e915b5f0d65e058419d3b8d3ae02589f28ca7d50",  # extension_freeze.move
    "5a9edcf0c56865c96d819b6873cd288ec3f117ca5171c391042d5173814608ff",  # Move Patterns in Frontier
    "478ee6fcd19f0418e0e90be2b253e0bb66e6977a8fb32cedee915f6e320c3d21",  # Build a Custom Turret Extension
    "f340891a6eb864ce9c23d13e672df3c11130d3c2ec5673f909674ecb6e7f33ef",  # Build a Custom Smart Gate
    "12342dfb485d08e523dc4c9d098e648b3193c6fed9628d1b56bb953570891098",  # issue-tribe-jump-permit.ts (authoritative_source)
    "07329c0be74ed6f340f6fc851da6722bbcead3574b7ed697d9a536bcc1e5b35c",  # jump-with-permit.ts
    "d431ef08d0f75bb81f5c55472bae22b262c54a46d2b4e8bd00a90b4a1f19f912",  # delete-jump-permit-extension.ts
    "38fb80f86150efcfa8d63b49de2f40902f8817473e3fa0c0a90fb5e723424e53",  # gate_tests.move
]

evidence = []
for rid in priority_ids:
    r = requests.get(f"{base}/api/records/{rid}")
    if r.status_code != 200:
        print(f"FAIL: {rid} returned {r.status_code}")
        continue
    
    d = r.json()
    text = d.get("text", "")
    snippet = text[:300] if text else ""
    
    evidence.append({
        "title": d["title"],
        "url": d["url"],
        "authority_tier": d["authority_tier"],
        "record_id": rid,
        "record_api_url": f"/api/records/{rid}",
        "snippet": snippet,
        "full_text": text
    })

print(json.dumps(evidence, indent=2))
