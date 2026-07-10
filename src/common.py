import os
import requests

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def sb_headers(prefer=None):
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h

def sb_get(table, params=None):
    r = requests.get(f"{SB_URL}/rest/v1/{table}", headers=sb_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def sb_post(table, payload, prefer="return=representation"):
    r = requests.post(f"{SB_URL}/rest/v1/{table}", headers=sb_headers(prefer), json=payload, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else []

def sb_patch(table, filters, payload):
    r = requests.patch(f"{SB_URL}/rest/v1/{table}", headers=sb_headers("return=minimal"), params=filters, json=payload, timeout=30)
    r.raise_for_status()

