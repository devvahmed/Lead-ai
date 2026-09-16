import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../backend")
from auth_models import SessionLocal, Company
from auth_utils import create_access_token
import urllib.request
import json

db = SessionLocal()
company = db.query(Company).first()
if not company:
    print("No company in db")
    sys.exit(1)

token = create_access_token({"sub": str(company.id), "email": company.email})
print(f"Testing with company: {company.name} ({company.email})")

payload = {
    "keyword": "Robotics",
    "country": "Canada",
    "city": "",
    "minTrustScore": 75,
    "pageno": 1,
    "target_count": 1
}

req = urllib.request.Request(
    "http://localhost:3000/api/discover-companies",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Status code:", resp.status)
        print("Content-Type:", resp.headers.get("content-type"))
        first_line = resp.readline().decode("utf-8")
        print("First line:", first_line[:200])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode("utf-8"))
except Exception as e:
    print("Error:", e)
