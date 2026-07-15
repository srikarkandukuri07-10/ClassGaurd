import requests
import json

print("Testing Render Backend Status...")
try:
    # Test wake up / GET sections endpoint
    r = requests.get("https://classguard-backend.onrender.com/api/students/sections", timeout=15)
    print(f"Status Code (GET /sections): {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Failed to connect: {e}")

try:
    # Test POST link-device endpoint
    payload = {"code": "CG-0XP6XC"}
    r = requests.post("https://classguard-backend.onrender.com/api/students/link-device", json=payload, timeout=15)
    print(f"Status Code (POST /link-device): {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Failed to link: {e}")
