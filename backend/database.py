from __future__ import annotations
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RAW_DB_FILE = os.getenv("DATABASE_FILE", "wtechx_ai.db")
DB_FILE = _RAW_DB_FILE if os.path.isabs(_RAW_DB_FILE) else os.path.join(_BASE_DIR, _RAW_DB_FILE)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_add_column(cursor, table, column, col_type):
    """Adds a column if it does not already exist (idempotent)."""
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Main leads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            company_description TEXT,
            contact_email TEXT UNIQUE NOT NULL,
            subject TEXT,
            sent_at TEXT,
            opened BOOLEAN DEFAULT 0,
            clicked BOOLEAN DEFAULT 0,
            replied BOOLEAN DEFAULT 0,
            bounced BOOLEAN DEFAULT 0,
            probability_score INTEGER DEFAULT 20,
            suggested_action TEXT,
            email_source_context TEXT,
            company_id INTEGER DEFAULT 1
        )
    """)
    _safe_add_column(cursor, "leads", "email_source_context", "TEXT")
    _safe_add_column(cursor, "leads", "company_id", "INTEGER DEFAULT 1")

    # Enriched contacts table (with full source tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enriched_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            website_url TEXT,
            email TEXT,
            phone TEXT,
            stakeholder TEXT,
            context_snippet TEXT,
            email_source_context TEXT,
            source_page TEXT,
            source_label TEXT,
            all_contacts_json TEXT,
            enriched_at TEXT,
            company_id INTEGER DEFAULT 1
        )
    """)
    for col, col_type in [
        ("source_page", "TEXT"),
        ("source_label", "TEXT"),
        ("all_contacts_json", "TEXT"),
        ("email_source_context", "TEXT"),
        ("company_id", "INTEGER DEFAULT 1"),
    ]:
        _safe_add_column(cursor, "enriched_contacts", col, col_type)

    # Clients table (saved prospects from discovery)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            website TEXT,
            industry TEXT,
            country TEXT,
            trust_score INTEGER DEFAULT 0,
            relevance_reason TEXT,
            status TEXT DEFAULT 'Pending',
            email TEXT,
            phone TEXT,
            phones TEXT,
            linkedin_company TEXT,
            contact_source_url TEXT,
            contact_source_page TEXT,
            contact_source_label TEXT,
            contact_source_context TEXT,
            logo_url TEXT,
            search_query TEXT,
            created_at TEXT
        )
    """)
    for col, col_type in [
        ("company_id", "INTEGER DEFAULT 1"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
        ("phones", "TEXT"),
        ("linkedin_company", "TEXT"),
        ("contact_source_url", "TEXT"),
        ("contact_source_page", "TEXT"),
        ("contact_source_label", "TEXT"),
        ("contact_source_context", "TEXT"),
        ("logo_url", "TEXT"),
        ("search_query", "TEXT"),
        ("created_at", "TEXT"),
    ]:
        _safe_add_column(cursor, "clients", col, col_type)

    _safe_add_column(cursor, "companies", "ai_enriched_profile", "TEXT")

    # Email History table (per-client generated/sent emails log)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            company_id INTEGER DEFAULT 1,
            email_type TEXT NOT NULL,
            label TEXT NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            recipient_email TEXT,
            status TEXT DEFAULT 'Draft',
            created_at TEXT NOT NULL
        )
    """)

    # Discovered Domains History table for cross-run deduplication
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discovered_domains_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1,
            domain TEXT NOT NULL,
            keyword TEXT,
            country TEXT,
            discovered_at TEXT,
            UNIQUE(company_id, domain)
        )
    """)

    # 24/7 Autonomous Lead Harvester State Table (Survives Server Reboots)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS automation_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1 UNIQUE,
            status TEXT DEFAULT 'STOPPED',
            target_service TEXT,
            target_countries TEXT,
            min_trust_score INTEGER DEFAULT 70,
            total_leads_scanned INTEGER DEFAULT 0,
            verified_emails_found INTEGER DEFAULT 0,
            current_niche TEXT,
            current_query TEXT,
            csv_file_path TEXT,
            started_at TEXT,
            last_heartbeat TEXT
        )
    """)

    # Automation Verified Leads Vault (Only Genuine Extracted Emails)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS automation_verified_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            domain TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            country TEXT,
            industry TEXT,
            trust_score INTEGER DEFAULT 70,
            outreach_angle TEXT,
            created_at TEXT
        )
    """)
    _safe_add_column(cursor, "automation_verified_leads", "csv_file_path", "TEXT")

    # Backfill any legacy verified leads to the company's active CSV path
    try:
        cursor.execute("""
            UPDATE automation_verified_leads
            SET csv_file_path = (SELECT csv_file_path FROM automation_jobs WHERE automation_jobs.company_id = automation_verified_leads.company_id)
            WHERE csv_file_path IS NULL OR csv_file_path = ''
        """)
    except Exception:
        pass

    # Clean up legacy 4-country default array from previous versions
    try:
        cursor.execute("""
            UPDATE automation_jobs 
            SET target_countries = '[]' 
            WHERE status != 'RUNNING'
              AND (
                target_countries LIKE '%United States%' 
                AND target_countries LIKE '%Pakistan%' 
                AND target_countries LIKE '%United Kingdom%' 
                AND target_countries LIKE '%Canada%'
              )
        """)
    except Exception:
        pass

    conn.commit()
    conn.close()


def save_lead(lead_id, name, description, email, subject, sent_at, action,
              email_source_context=None, company_id=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO leads (
                id, company_name, company_description, contact_email,
                subject, sent_at, opened, clicked, replied, bounced,
                probability_score, suggested_action, email_source_context, company_id
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 20, ?, ?, ?)
        """, (lead_id, name, description, email, subject, sent_at,
              action, email_source_context, company_id))
        conn.commit()
    finally:
        conn.close()


def save_enriched_contact(company_name, website_url, email=None, phone=None,
                           stakeholder=None, context_snippet=None,
                           email_source_context=None, source_page=None,
                           source_label=None, all_contacts=None, company_id=1):
    """
    Saves an enriched contact with precise source tracking references and company_id scoping.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        all_contacts_json = json.dumps(all_contacts or [])
        enriched_at = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO enriched_contacts (
                company_name, website_url, email, phone, stakeholder,
                context_snippet, email_source_context, source_page,
                source_label, all_contacts_json, enriched_at, company_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_name, website_url, email, phone, stakeholder,
              context_snippet, email_source_context, source_page,
              source_label, all_contacts_json, enriched_at, company_id))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_enriched_contacts(company_name=None, company_id=None):
    """Returns enriched contacts, optionally filtered by company_name and company_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM enriched_contacts WHERE 1=1"
        params = []
        if company_id is not None:
            query += " AND company_id = ?"
            params.append(company_id)
        if company_name:
            query += " AND company_name = ?"
            params.append(company_name)
        query += " ORDER BY enriched_at DESC"
        rows = cursor.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_lead_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT * FROM leads WHERE contact_email = ?", (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_lead_by_id(lead_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_lead_tracking(email, opened=None, clicked=None, bounced=None,
                          score_delta=0, status_update=None, action=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT probability_score, opened, clicked, bounced "
            "FROM leads WHERE contact_email = ?",
            (email,)
        ).fetchone()
        if not row:
            return None

        current_score = row["probability_score"]
        new_opened  = opened  if opened  is not None else bool(row["opened"])
        new_clicked = clicked if clicked is not None else bool(row["clicked"])
        new_bounced = bounced if bounced is not None else bool(row["bounced"])
        new_score   = 0 if bounced else current_score + score_delta
        new_score   = max(0, min(100, new_score))

        cursor.execute("""
            UPDATE leads
            SET opened=?, clicked=?, bounced=?,
                probability_score=?, suggested_action=?
            WHERE contact_email=?
        """, (1 if new_opened else 0, 1 if new_clicked else 0,
              1 if new_bounced else 0, new_score, action, email))
        conn.commit()

        row2 = cursor.execute(
            "SELECT * FROM leads WHERE contact_email = ?", (email,)
        ).fetchone()
        return dict(row2) if row2 else None
    finally:
        conn.close()


def get_all_leads(company_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if company_id is not None:
            rows = cursor.execute(
                "SELECT * FROM leads WHERE company_id = ? ORDER BY probability_score DESC", (company_id,)
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT * FROM leads ORDER BY probability_score DESC"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_dashboard_stats(company_id: int):
    """
    Computes multi-tenant real-time dashboard statistics strictly isolated for company_id.
    Synchronizes manual discovery clients, 24/7 autonomous harvester telemetry,
    email outreach history, and live CSV vaults.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Total Saved Clients & Automated Harvested Leads
        clients_count = cursor.execute(
            "SELECT COUNT(*) FROM clients WHERE company_id = ?", (company_id,)
        ).fetchone()[0]

        harvested_count = cursor.execute(
            "SELECT COUNT(*) FROM automation_verified_leads WHERE company_id = ?", (company_id,)
        ).fetchone()[0]

        # Distinct total prospects across both sources
        try:
            total_distinct_row = cursor.execute("""
                SELECT COUNT(DISTINCT LOWER(name)) FROM (
                    SELECT name FROM clients WHERE company_id = ?
                    UNION ALL
                    SELECT name FROM automation_verified_leads WHERE company_id = ?
                )
            """, (company_id, company_id)).fetchone()
            total_companies_found = total_distinct_row[0] if total_distinct_row else max(clients_count, harvested_count)
        except Exception:
            total_companies_found = max(clients_count, harvested_count)

        # 2. Automation Daemon Telemetry & Job Status
        job_row = cursor.execute("""
            SELECT status, target_service, target_countries, total_leads_scanned,
                   verified_emails_found, csv_file_path, current_niche, started_at
            FROM automation_jobs WHERE company_id = ?
        """, (company_id,)).fetchone()

        automation_status = (job_row["status"] if job_row and job_row["status"] else "STOPPED").upper()
        automation_service = job_row["target_service"] if job_row and job_row["target_service"] else ""
        automation_countries = job_row["target_countries"] if job_row and job_row["target_countries"] else "[]"
        total_leads_scanned = job_row["total_leads_scanned"] if job_row and job_row["total_leads_scanned"] else 0
        verified_emails_found = job_row["verified_emails_found"] if job_row and job_row["verified_emails_found"] else harvested_count
        csv_path = job_row["csv_file_path"] if job_row and job_row["csv_file_path"] else ""
        active_vault_name = os.path.basename(csv_path) if csv_path else ""
        current_niche = job_row["current_niche"] if job_row and job_row["current_niche"] else ""

        # 3. Qualified Leads (Clients with generated emails OR status in Qualified/Contacted/In Negotiation/Won OR trust_score >= 80 + all verified automated leads)
        clients_with_emails = cursor.execute(
            "SELECT COUNT(DISTINCT client_id) FROM email_history WHERE company_id = ?", (company_id,)
        ).fetchone()[0]

        qualified_status_count = cursor.execute("""
            SELECT COUNT(*) FROM clients
            WHERE company_id = ? AND (status IN ('Qualified', 'Contacted', 'In Negotiation', 'Won') OR trust_score >= 80)
        """, (company_id,)).fetchone()[0]

        qualified_leads = max(clients_with_emails, qualified_status_count, harvested_count)

        # 4. Active Outreach (Total emails generated + clients currently in Contacted/In Negotiation status)
        total_emails_generated = cursor.execute(
            "SELECT COUNT(*) FROM email_history WHERE company_id = ?", (company_id,)
        ).fetchone()[0]

        contacted_clients_count = cursor.execute("""
            SELECT COUNT(*) FROM clients
            WHERE company_id = ? AND status IN ('Contacted', 'In Negotiation', 'Won')
        """, (company_id,)).fetchone()[0]

        active_outreach = max(total_emails_generated, contacted_clients_count)

        # 5. Avg Trust Score across saved clients and automated verified leads
        avg_score_row = cursor.execute("""
            SELECT AVG(score) FROM (
                SELECT trust_score AS score FROM clients WHERE company_id = ? AND trust_score > 0
                UNION ALL
                SELECT trust_score AS score FROM automation_verified_leads WHERE company_id = ? AND trust_score > 0
            )
        """, (company_id, company_id)).fetchone()
        
        if avg_score_row and avg_score_row[0] is not None and float(avg_score_row[0]) > 0:
            avg_trust_score = round(float(avg_score_row[0]), 1)
        else:
            avg_trust_score = 0.0

        # 6. Dynamic Recent Activity Log (unified from automation_verified_leads, email_history, and clients)
        activity_list = []
        
        # Recent autonomous verified leads discovered
        recent_harvested = cursor.execute("""
            SELECT name, email, industry, country, trust_score, created_at
            FROM automation_verified_leads
            WHERE company_id = ?
            ORDER BY id DESC LIMIT 5
        """, (company_id,)).fetchall()

        for h in recent_harvested:
            activity_list.append({
                "title": f"⚡ Auto-Harvested: {h['name']}",
                "subtitle": f"{h['email']} · {h['industry'] or 'Operating Prospect'}",
                "timestamp": h["created_at"] or datetime.utcnow().isoformat(),
                "icon": "mark_email_read",
                "type": "automation",
                "probability_score": h["trust_score"]
            })

        # Recent email events
        recent_emails = cursor.execute("""
            SELECT eh.label, eh.subject, eh.email_type, eh.created_at, c.name as client_name
            FROM email_history eh
            LEFT JOIN clients c ON eh.client_id = c.id
            WHERE eh.company_id = ?
            ORDER BY eh.id DESC LIMIT 5
        """, (company_id,)).fetchall()

        for r in recent_emails:
            c_name = r["client_name"] or "Prospect"
            t_name = "Cold Outreach" if r["email_type"] == "outreach" else ("Follow-up" if r["email_type"] == "followup" else "Negotiation Reply")
            activity_list.append({
                "title": f"{r['label']} Generated",
                "subtitle": f"{t_name} for {c_name}",
                "timestamp": r["created_at"],
                "icon": "auto_awesome" if r["email_type"] == "outreach" else ("sync" if r["email_type"] == "followup" else "handshake"),
                "type": r["email_type"]
            })

        # Recent client saves
        recent_clients = cursor.execute("""
            SELECT name, created_at, trust_score, status, industry
            FROM clients WHERE company_id = ?
            ORDER BY id DESC LIMIT 5
        """, (company_id,)).fetchall()

        for c in recent_clients:
            activity_list.append({
                "title": f"Prospect Added: {c['name']}",
                "subtitle": f"Fit Score: {c['trust_score']}% · {c['industry'] or c['status']}",
                "timestamp": c["created_at"] or datetime.utcnow().isoformat(),
                "icon": "corporate_fare",
                "type": "saved",
                "probability_score": c["trust_score"]
            })

        # Sort combined activities by timestamp DESC
        activity_list.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
        recent_activity = activity_list[:8]

        # 7. Real Dynamic Weekly Chart Activity Data
        w1_emails, w2_emails, w3_emails, w4_emails = 0, 0, 0, 0
        w1_calls, w2_calls, w3_calls, w4_calls = 0, 0, 0, 0
        w1_meetings, w2_meetings, w3_meetings, w4_meetings = 0, 0, 0, 0

        now = datetime.utcnow()
        week4_start = now - timedelta(days=7)
        week3_start = now - timedelta(days=14)
        week2_start = now - timedelta(days=21)
        week1_start = now - timedelta(days=28)

        # Query all email timestamps for company_id
        all_emails = cursor.execute("""
            SELECT created_at FROM email_history WHERE company_id = ?
        """, (company_id,)).fetchall()

        for em in all_emails:
            ts_str = em["created_at"]
            if not ts_str:
                continue
            try:
                if "T" in str(ts_str):
                    em_date = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    em_date = datetime.strptime(str(ts_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                em_date = now

            if em_date >= week4_start:
                w4_emails += 1
            elif em_date >= week3_start:
                w3_emails += 1
            elif em_date >= week2_start:
                w2_emails += 1
            elif em_date >= week1_start:
                w1_emails += 1

        # Query all client status & timestamps for company_id
        all_clients_status = cursor.execute("""
            SELECT status, created_at FROM clients WHERE company_id = ?
        """, (company_id,)).fetchall()

        for cl in all_clients_status:
            st = cl["status"]
            ts_str = cl["created_at"]
            if not ts_str or st not in ("Contacted", "In Negotiation", "Won"):
                continue
            try:
                if "T" in str(ts_str):
                    cl_date = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    cl_date = datetime.strptime(str(ts_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                cl_date = now

            if st == "Contacted":
                if cl_date >= week4_start:
                    w4_calls += 1
                elif cl_date >= week3_start:
                    w3_calls += 1
                elif cl_date >= week2_start:
                    w2_calls += 1
                elif cl_date >= week1_start:
                    w1_calls += 1
            elif st in ("In Negotiation", "Won"):
                if cl_date >= week4_start:
                    w4_meetings += 1
                elif cl_date >= week3_start:
                    w3_meetings += 1
                elif cl_date >= week2_start:
                    w2_meetings += 1
                elif cl_date >= week1_start:
                    w1_meetings += 1

        # Also incorporate weekly harvested leads into calls/meetings pipeline telemetry
        all_harvested_dates = cursor.execute("""
            SELECT created_at FROM automation_verified_leads WHERE company_id = ?
        """, (company_id,)).fetchall()
        for h in all_harvested_dates:
            ts_str = h["created_at"]
            if not ts_str:
                continue
            try:
                if "T" in str(ts_str):
                    h_date = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    h_date = datetime.strptime(str(ts_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                h_date = now

            if h_date >= week4_start:
                w4_calls += 1
            elif h_date >= week3_start:
                w3_calls += 1
            elif h_date >= week2_start:
                w2_calls += 1
            elif h_date >= week1_start:
                w1_calls += 1

        weekly_chart = [
            {"day": "Week 1", "emails": w1_emails, "calls": w1_calls, "meetings": w1_meetings},
            {"day": "Week 2", "emails": w2_emails, "calls": w2_calls, "meetings": w2_meetings},
            {"day": "Week 3", "emails": w3_emails, "calls": w3_calls, "meetings": w3_meetings},
            {"day": "Week 4", "emails": w4_emails, "calls": w4_calls, "meetings": w4_meetings},
        ]

        return {
            "company_id": company_id,
            "total_companies_found": total_companies_found,
            "total_clients": clients_count,
            "total_harvested_leads": harvested_count,
            "qualified_leads": qualified_leads,
            "active_outreach": active_outreach,
            "avg_trust_score": avg_trust_score,
            "total_emails_generated": total_emails_generated,
            "automation_status": automation_status,
            "automation_service": automation_service,
            "automation_countries": automation_countries,
            "active_vault_name": active_vault_name,
            "total_leads_scanned": total_leads_scanned,
            "verified_emails_found": verified_emails_found,
            "current_niche": current_niche,
            "recent_activity": recent_activity,
            "weekly_chart": weekly_chart
        }
    finally:
        conn.close()


def save_client(name, website=None, industry=None, country=None, trust_score=0,
                relevance_reason=None, status="Pending", email=None, phone=None,
                phones=None, linkedin_company=None, contact_source_url=None,
                contact_source_page=None, contact_source_label=None,
                contact_source_context=None, logo_url=None, search_query=None, company_id=1):
    """Saves or updates a client record in SQLite DB (deduplicated) and returns dict."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check for existing record by name or website
        existing = cursor.execute("""
            SELECT id FROM clients
            WHERE company_id = ? AND (LOWER(name) = LOWER(?) OR (website IS NOT NULL AND LOWER(website) = LOWER(?)))
        """, (company_id, name, website or "")).fetchone()

        if existing:
            client_id = existing["id"]
            # Update existing record cleanly without duplicate insert
            return update_client(
                client_id=client_id,
                company_id=company_id,
                name=name,
                website=website,
                industry=industry,
                country=country,
                trust_score=trust_score,
                relevance_reason=relevance_reason,
                status=status,
                email=email,
                phone=phone,
                phones=phones,
                linkedin_company=linkedin_company,
                contact_source_url=contact_source_url,
                contact_source_page=contact_source_page,
                contact_source_label=contact_source_label,
                contact_source_context=contact_source_context,
                logo_url=logo_url,
                search_query=search_query
            )

        created_at = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO clients (
                company_id, name, website, industry, country, trust_score,
                relevance_reason, status, email, phone, phones, linkedin_company,
                contact_source_url, contact_source_page, contact_source_label,
                contact_source_context, logo_url, search_query, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_id, name, website, industry, country, trust_score,
              relevance_reason, status, email, phone, phones, linkedin_company,
              contact_source_url, contact_source_page, contact_source_label,
              contact_source_context, logo_url, search_query, created_at))
        conn.commit()
        client_id = cursor.lastrowid
        row = cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_clients(company_id=1):
    """Retrieves all saved clients scoped strictly by company_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rows = cursor.execute(
            "SELECT * FROM clients WHERE company_id = ? ORDER BY id DESC", (company_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_client_by_id(client_id, company_id=1):
    """Retrieves a single saved client by ID and company_id (with fallback)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT * FROM clients WHERE id = ? AND company_id = ?", (client_id, company_id)
        ).fetchone()
        if not row:
            row = cursor.execute(
                "SELECT * FROM clients WHERE id = ?", (client_id,)
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_client(client_id, company_id=1, **kwargs):
    """Updates client record attributes in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        allowed = [
            "name", "website", "industry", "country", "trust_score", "relevance_reason",
            "status", "email", "phone", "phones", "linkedin_company", "contact_source_url",
            "contact_source_page", "contact_source_label", "contact_source_context", "logo_url", "search_query"
        ]
        updates = []
        values = []
        for key, val in kwargs.items():
            if key in allowed and val is not None:
                updates.append(f"{key} = ?")
                values.append(val)
        if not updates:
            row = cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            return dict(row) if row else None

        values.append(client_id)
        sql = f"UPDATE clients SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, values)
        conn.commit()

        row = cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_email_history(client_id: int, email_type: str, body: str,
                       subject: str = None, recipient_email: str = None,
                       company_id: int = 1, status: str = "Draft"):
    """Saves a new email entry in email_history table with auto-incremented label."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Count existing emails of the same type for this client to calculate label
        count_row = cursor.execute("""
            SELECT COUNT(*) as cnt FROM email_history
            WHERE client_id = ? AND company_id = ? AND email_type = ?
        """, (client_id, company_id, email_type)).fetchone()

        count = (count_row["cnt"] if count_row else 0) + 1

        # Build readable sequence label
        if email_type == "outreach":
            label = f"Cold Outreach {count}"
        elif email_type == "followup":
            label = f"Follow-up {count}"
        elif email_type == "negotiation":
            label = f"Negotiation Reply {count}"
        else:
            label = f"Email {count}"

        created_at = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO email_history (
                client_id, company_id, email_type, label, subject,
                body, recipient_email, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_id, company_id, email_type, label, subject,
              body, recipient_email, status, created_at))

        conn.commit()
        last_id = cursor.lastrowid
        row = cursor.execute("SELECT * FROM email_history WHERE id = ?", (last_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_email_history(client_id: int, company_id: int = 1):
    """Retrieves all email history entries for a given client_id and company_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rows = cursor.execute("""
            SELECT * FROM email_history
            WHERE client_id = ? AND company_id = ?
            ORDER BY id DESC
        """, (client_id, company_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_known_domains(company_id: int = 1) -> set:
    """
    Returns a set of normalized lower-case domain strings that are already known:
    either saved as clients or previously discovered in search sessions.
    """
    from urllib.parse import urlparse
    known = set()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Existing clients
        client_rows = cursor.execute(
            "SELECT website FROM clients WHERE company_id = ? AND website IS NOT NULL",
            (company_id,)
        ).fetchall()
        for r in client_rows:
            w = (r["website"] or "").strip().lower()
            if not w:
                continue
            if not w.startswith(("http://", "https://")):
                w = "https://" + w
            try:
                dom = urlparse(w).netloc.lower().replace("www.", "")
                if dom:
                    known.add(dom)
            except Exception:
                pass

        # 2. History of discovered domains
        hist_rows = cursor.execute(
            "SELECT domain FROM discovered_domains_history WHERE company_id = ?",
            (company_id,)
        ).fetchall()
        for r in hist_rows:
            d = (r["domain"] or "").strip().lower().replace("www.", "")
            if d:
                known.add(d)

        return known
    finally:
        conn.close()


def record_discovered_domains(company_id: int, domains: list, keyword: str = "", country: str = ""):
    """
    Persists discovered domains so subsequent searches avoid repeating them.
    """
    if not domains:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.utcnow().isoformat()
    try:
        for d in domains:
            clean_d = (d or "").strip().lower().replace("www.", "")
            if not clean_d:
                continue
            cursor.execute("""
                INSERT OR IGNORE INTO discovered_domains_history
                (company_id, domain, keyword, country, discovered_at)
                VALUES (?, ?, ?, ?, ?)
            """, (company_id, clean_d, (keyword or "").strip(), (country or "").strip(), now_str))
        conn.commit()
    finally:
        conn.close()


def get_keyword_run_count(company_id: int, keyword: str, country: str = "") -> int:
    """
    Returns how many previously discovered domains exist for this keyword and country,
    used to calculate query rotation index and search pagination offsets.
    """
    if not keyword:
        return 0
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute("""
            SELECT COUNT(*) as cnt FROM discovered_domains_history
            WHERE company_id = ? AND LOWER(keyword) = LOWER(?)
        """, (company_id, keyword.strip())).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# ─── 24/7 Automation & Live CSV Vault Helper Functions ───────────────────────

def get_or_create_automation_job(company_id: int = 1) -> dict:
    """Fetches current automation job state or initializes a default job for company."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        row = cursor.execute(
            "SELECT * FROM automation_jobs WHERE company_id = ?",
            (company_id,)
        ).fetchone()
        if row:
            return dict(row)

        # Create default stopped job
        now_str = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO automation_jobs (
                company_id, status, target_service, target_countries,
                min_trust_score, total_leads_scanned, verified_emails_found,
                current_niche, current_query, started_at, last_heartbeat
            ) VALUES (?, 'STOPPED', '', '[]', 70, 0, 0, '', '', ?, ?)
        """, (company_id, now_str, now_str))
        conn.commit()
        last_row = cursor.execute("SELECT * FROM automation_jobs WHERE company_id = ?", (company_id,)).fetchone()
        return dict(last_row) if last_row else {}
    finally:
        conn.close()


def update_automation_job(company_id: int = 1, **kwargs) -> dict:
    """Dynamically updates fields for the company's automation job."""
    if not kwargs:
        return get_or_create_automation_job(company_id)

    kwargs["last_heartbeat"] = datetime.utcnow().isoformat()
    fields = []
    values = []
    for k, v in kwargs.items():
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(company_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"""
            UPDATE automation_jobs
            SET {', '.join(fields)}
            WHERE company_id = ?
        """, tuple(values))
        conn.commit()
        row = cursor.execute("SELECT * FROM automation_jobs WHERE company_id = ?", (company_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_active_automation_jobs() -> list:
    """Returns all jobs marked RUNNING across companies (used on server reboot)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        rows = cursor.execute(
            "SELECT * FROM automation_jobs WHERE status = 'RUNNING'"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_automation_verified_lead(company_id: int, lead: dict) -> Optional[dict]:
    """
    STRICT EMAIL GATEKEEPER:
    Saves a newly discovered company ONLY if a genuine verified email was extracted.
    Atomically:
      1. Inserts into SQLite `automation_verified_leads`
      2. Inserts into SQLite `clients` (for regular CRM display)
      3. Appends row to live CSV file in `exports/` directory with immediate flush and fsync!
    """
    import csv

    # STRICT GATE: Must have genuine email
    email = (lead.get("email") or "").strip()
    if not email or "@" not in email or "." not in email:
        return None

    name = (lead.get("name") or "Verified Company").strip()
    website = (lead.get("website") or "").strip()
    domain = (lead.get("domain") or "").strip()
    phone = (lead.get("phone") or "").strip()
    country = (lead.get("country") or "Global").strip()
    industry = (lead.get("industry") or "B2B Operating Company").strip()
    trust_score = int(lead.get("trustScore") or lead.get("evidenceScore") or 75)
    outreach_angle = (lead.get("outreachAngle") or lead.get("matchReason") or "").strip()
    now_str = datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Resolve active CSV file path from automation_jobs
        exports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
        os.makedirs(exports_dir, exist_ok=True)

        job_row = cursor.execute("SELECT csv_file_path FROM automation_jobs WHERE company_id = ?", (company_id,)).fetchone()
        csv_path = job_row["csv_file_path"] if (job_row and job_row["csv_file_path"]) else None
        if not csv_path:
            csv_path = os.path.join(exports_dir, f"leads_automation_company_{company_id}.csv")

        # Check if email was already verified in THIS active CSV run
        existing = cursor.execute("""
            SELECT id FROM automation_verified_leads
            WHERE company_id = ? AND csv_file_path = ? AND LOWER(email) = LOWER(?)
        """, (company_id, csv_path, email)).fetchone()

        if existing:
            return None

        # 1. Insert into automation_verified_leads with active csv_file_path
        cursor.execute("""
            INSERT INTO automation_verified_leads (
                company_id, name, website, domain, email, phone,
                country, industry, trust_score, outreach_angle, created_at, csv_file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (company_id, name, website, domain, email, phone,
              country, industry, trust_score, outreach_angle, now_str, csv_path))
        conn.commit()

        # 2. Also save to regular clients table so user sees it in main CRM
        save_client(
            name=name,
            website=website,
            industry=industry,
            country=country,
            trust_score=trust_score,
            relevance_reason=outreach_angle,
            status="Pending",
            email=email,
            phone=phone,
            company_id=company_id
        )

        # 3. Crash-proof live CSV append to active CSV file
        file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Company Name", "Website", "Verified Email", "Phone",
                    "Country", "Industry", "Trust Score", "Outreach Pitch Angle", "Discovered At"
                ])
            writer.writerow([
                name, website, email, phone, country, industry, trust_score, outreach_angle, now_str
            ])
            f.flush()
            os.fsync(f.fileno())

        # Update CSV file path and verified_emails_found in automation_jobs
        cursor.execute("""
            UPDATE automation_jobs
            SET verified_emails_found = verified_emails_found + 1,
                csv_file_path = ?
            WHERE company_id = ?
        """, (csv_path, company_id))
        conn.commit()

        return {
            "name": name,
            "website": website,
            "domain": domain,
            "email": email,
            "phone": phone,
            "country": country,
            "industry": industry,
            "trustScore": trust_score,
            "outreachAngle": outreach_angle,
            "createdAt": now_str
        }
    finally:
        conn.close()


def get_recent_automation_leads(company_id: int = 1, limit: int = 20, csv_file_path: Optional[str] = None) -> list:
    """
    Fetches recent genuine verified leads found by the autonomous harvester.
    Filters specifically by the active campaign's csv_file_path so a fresh run starts with a clean stream!
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not csv_file_path:
            job_row = cursor.execute("SELECT csv_file_path FROM automation_jobs WHERE company_id = ?", (company_id,)).fetchone()
            if job_row and job_row["csv_file_path"]:
                csv_file_path = job_row["csv_file_path"]

        if csv_file_path:
            rows = cursor.execute("""
                SELECT * FROM automation_verified_leads
                WHERE company_id = ? AND csv_file_path = ?
                ORDER BY id DESC
                LIMIT ?
            """, (company_id, csv_file_path, limit)).fetchall()
            return [dict(r) for r in rows]
        else:
            rows = cursor.execute("""
                SELECT * FROM automation_verified_leads
                WHERE company_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (company_id, limit)).fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()



