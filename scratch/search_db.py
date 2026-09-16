import sqlite3
import glob
import os

for f in glob.glob("**/*.db", recursive=True):
    try:
        conn = sqlite3.connect(f)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for t in tables:
            tname = t[0]
            try:
                rows = conn.execute(f"SELECT * FROM {tname}").fetchall()
                for row in rows:
                    r_str = str(row).lower()
                    if any(w in r_str for w in ["sbortix", "sportix", "education", "wtechx"]):
                        print(f"FOUND in {f} table {tname}: {row}")
            except Exception as e:
                pass
    except Exception as e:
        print(f"Error {f}: {e}")
print("Search complete.")
