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
    
    # Extract snippet (first 300 chars, preserve newlines for code)
    snippet = text[:300] if text else ""
    
    evidence.append({
        "title": rec["title"],
        "url": rec["url"],
        "authority_tier": rec["authority_tier"],
        "record_id": rid,
        "snippet": snippet,
        "full_text": text
    })

# Print as markdown table
print("| Title | URL | Authority Tier | Record ID | Snippet | What it says about smart-gate extension authorization |")
print("|-------|-----|----------------|------------|---------|------------------------------------------------------|")
for item in evidence:
    title = item["title"][:50]
    url = item["url"][:60]
    tier = item["authority_tier"]
    rid = item["record_id"][:20]
    snippet = item["snippet"].replace("\n", " ")[:100]
    print(f"| {title} | {url} | {tier} | {rid} | {snippet} | [To be filled] |")
