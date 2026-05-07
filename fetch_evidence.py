#!/usr/bin/env python3
import requests
import json

base = "http://127.0.0.1:8000"

# Get top 10 records from smart-gates context
ctx = requests.get(f"{base}/api/context/smart-gates").json()
top_records = ctx["top_records"][:10]

evidence = []
for rec in top_records:
    rid = rec["id"]
    # Fetch full record
    r = requests.get(f"{base}/api/records/{rid}")
    if r.status_code != 200:
        print(f"FAIL: {rid} returned {r.status_code}")
        continue
    
    full = r.json()
    text = full.get("text", "")
    
    # Extract snippet (first 200 chars)
    snippet = text[:200].replace("\n", " ") if text else ""
    
    evidence.append({
        "title": rec["title"],
        "url": rec["url"],
        "authority_tier": rec["authority_tier"],
        "record_id": rid,
        "snippet": snippet,
        "full_text": text
    })

print(json.dumps(evidence, indent=2))
