import urllib.request
import urllib.error
import json

# Test GET without auth (should be 401 Unauthorized because it's protected by get_current_company, NOT 404!)
try:
    req = urllib.request.Request("http://localhost:8000/discover-companies")
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print("Direct Backend Status:", e.code, e.reason)

# Test Next.js proxy route /api/discover-companies without auth
try:
    req = urllib.request.Request("http://localhost:3000/api/discover-companies?keyword=Robotics")
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print("Next.js Proxy Status:", e.code, e.read().decode('utf-8'))
