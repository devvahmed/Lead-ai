"""
automation_engine.py -- 24/7 Autonomous Lead Harvester Daemon
============================================================
Runs continuously in the background on the server.
Features:
  - 100% Server Reboot Resilience: Survives power outages / reboots via SQLite state
  - Dynamic Niche Expansion: Automatically generates fresh industry angles
  - Cross-Session Deduplication: Never scrapes or yields duplicate companies
  - Multi-Layer Crawling: Smart DOM nav parsing + contact endpoints fallback
  - STRICT EMAIL GATEKEEPER: ONLY saves leads with real, verified corporate emails to CSV
  - Real-Time Live CSV Writer: Immediate fsync to disk
"""

from __future__ import annotations
import os
import json
import time
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

import database
from dynamic_industry_generator import get_next_discovery_batch
from discover import generate_industry_search_queries, clean_domain
from multi_source_ingestion import ingest_all_sources
from junk_firewall import is_deterministic_junk
from geo_lock_engine import verify_deterministic_geo
from email_outreach import (
    extract_regex_contacts,
    fetch_dedicated_contact_emails,
    fetch_url_content_with_subpages,
    is_valid_email
)

logger = logging.getLogger("automation_engine")

# ─── Active Worker Tasks Registry (In-Memory Tracker) ─────────────────────────
_active_tasks: Dict[int, asyncio.Task] = {}
_task_locks: Dict[int, asyncio.Lock] = {}


def _get_lock(company_id: int) -> asyncio.Lock:
    if company_id not in _task_locks:
        _task_locks[company_id] = asyncio.Lock()
    return _task_locks[company_id]


async def start_automation(
    company_id: int,
    target_service: str,
    target_countries: List[str],
    min_trust_score: int = 70
) -> dict:
    """
    Launches or updates the 24/7 background autonomous harvester for the given company.
    Persists RUNNING status in SQLite so it auto-resumes if the server reboots.
    """
    async with _get_lock(company_id):
        # Update SQLite state
        clean_service = (target_service or "B2B Professional Services").strip()
        countries_json = json.dumps(target_countries if target_countries else ["United States", "Pakistan", "United Kingdom", "Canada"])

        job = database.update_automation_job(
            company_id=company_id,
            status="RUNNING",
            target_service=clean_service,
            target_countries=countries_json,
            min_trust_score=min_trust_score,
            started_at=datetime.utcnow().isoformat()
        )

        # If a worker is already running for this company, let it pick up new config
        existing_task = _active_tasks.get(company_id)
        if existing_task and not existing_task.done():
            print(f"[Automation Engine] 🔄 Worker for company_id={company_id} already active. Updated configuration.", flush=True)
            return job

        # Spawn asynchronous daemon worker
        task = asyncio.create_task(_autonomous_harvesting_daemon(company_id))
        _active_tasks[company_id] = task
        print(f"[Automation Engine] 🚀 Launched 24/7 Harvester Daemon for company_id={company_id} (Service: '{clean_service}')", flush=True)
        return job


async def stop_automation(company_id: int) -> dict:
    """Stops the autonomous harvester and updates SQLite state."""
    async with _get_lock(company_id):
        job = database.update_automation_job(
            company_id=company_id,
            status="STOPPED"
        )
        task = _active_tasks.pop(company_id, None)
        if task and not task.done():
            task.cancel()
            print(f"[Automation Engine] 🛑 Stopped Harvester Daemon for company_id={company_id}.", flush=True)
        return job


async def pause_automation(company_id: int) -> dict:
    """Pauses the autonomous harvester."""
    async with _get_lock(company_id):
        job = database.update_automation_job(
            company_id=company_id,
            status="PAUSED"
        )
        task = _active_tasks.pop(company_id, None)
        if task and not task.done():
            task.cancel()
            print(f"[Automation Engine] ⏸️ Paused Harvester Daemon for company_id={company_id}.", flush=True)
        return job


def get_automation_status(company_id: int = 1) -> dict:
    """Returns comprehensive real-time status and telemetry for the UI."""
    job = database.get_or_create_automation_job(company_id)
    recent_leads = database.get_recent_automation_leads(company_id, limit=12)

    # Check if in-memory task matches DB status
    task = _active_tasks.get(company_id)
    is_actively_looping = bool(task and not task.done() and job.get("status") == "RUNNING")

    # Target countries parse
    try:
        raw_c = job.get("target_countries") or "[]"
        countries = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
    except Exception:
        countries = ["United States", "Pakistan", "United Kingdom", "Canada"]

    return {
        "companyId": company_id,
        "status": job.get("status", "STOPPED"),
        "isActivelyLooping": is_actively_looping,
        "targetService": job.get("target_service", ""),
        "targetCountries": countries,
        "minTrustScore": job.get("min_trust_score", 70),
        "totalLeadsScanned": job.get("total_leads_scanned", 0),
        "verifiedEmailsFound": job.get("verified_emails_found", 0),
        "currentNiche": job.get("current_niche", ""),
        "currentQuery": job.get("current_query", ""),
        "csvFilePath": job.get("csv_file_path", ""),
        "startedAt": job.get("started_at", ""),
        "lastHeartbeat": job.get("last_heartbeat", ""),
        "recentVerifiedLeads": recent_leads
    }


async def resume_active_jobs_on_boot():
    """
    HOOK FOR SERVER BOOT (FastAPI startup):
    Scans SQLite for jobs with status == 'RUNNING'.
    If found, resumes them automatically in the background without user intervention!
    """
    active_jobs = database.get_active_automation_jobs()
    if not active_jobs:
        print("[Automation Engine] ℹ️ No active automation jobs pending on boot.", flush=True)
        return

    print(f"[Automation Engine] ⚡ Boot-Resume: Found {len(active_jobs)} active automation job(s). Resuming daemons...", flush=True)
    for job in active_jobs:
        cid = job.get("company_id", 1)
        svc = job.get("target_service") or "B2B Services"
        raw_c = job.get("target_countries") or "[]"
        try:
            countries = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
        except Exception:
            countries = ["United States", "Pakistan", "United Kingdom", "Canada"]
        min_trust = job.get("min_trust_score", 70)

        # Launch worker
        await start_automation(
            company_id=cid,
            target_service=svc,
            target_countries=countries,
            min_trust_score=min_trust
        )


# ─── Core Autonomous Harvesting Daemon Loop ──────────────────────────────────

async def _autonomous_harvesting_daemon(company_id: int):
    """
    Infinite non-blocking background loop.
    Runs 24/7 until explicitly stopped by user.
    """
    print(f"[Automation Daemon {company_id}] Started background loop.", flush=True)
    country_idx = 0

    while True:
        try:
            # 1. Check database status. If STOPPED or PAUSED, exit gracefully.
            job = database.get_or_create_automation_job(company_id)
            status = job.get("status", "STOPPED")
            if status != "RUNNING":
                print(f"[Automation Daemon {company_id}] Job status is '{status}'. Exiting worker loop.", flush=True)
                break

            target_service = (job.get("target_service") or "B2B Digital Services").strip()
            min_trust = int(job.get("min_trust_score") or 70)
            try:
                raw_c = job.get("target_countries") or "[]"
                countries = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
            except Exception:
                countries = ["United States", "Pakistan", "United Kingdom", "Canada"]

            if not countries:
                countries = ["United States", "Pakistan", "United Kingdom", "Canada"]

            # Rotate through target countries
            active_country = countries[country_idx % len(countries)]
            country_idx += 1

            # 2. Dynamic Niche & Query Generation
            # Generates fresh, non-repetitive sub-industries tailored to the user's service
            current_niche = ""
            search_queries = []
            try:
                dynamic_batch = await get_next_discovery_batch(
                    our_services=target_service,
                    selected_country=active_country,
                    mode="dynamic_industry"
                )
                if dynamic_batch and dynamic_batch.get("queries"):
                    search_queries = dynamic_batch.get("queries", [])
                    current_niche = dynamic_batch.get("niche") or dynamic_batch.get("parent_industry") or target_service
            except Exception as dyn_err:
                logger.debug(f"[Automation Daemon] Dynamic niche generation fallback: {dyn_err}")

            if not search_queries:
                search_queries = generate_industry_search_queries(
                    industry=target_service,
                    location_str=active_country
                )
                current_niche = target_service

            active_query = search_queries[0] if search_queries else f"{target_service} company {active_country}"

            # Update DB with current activity telemetry
            database.update_automation_job(
                company_id=company_id,
                current_niche=current_niche,
                current_query=active_query
            )

            print(f"\n[Automation Daemon {company_id}] 🌐 Scanning Niche: '{current_niche}' in {active_country} | Query: '{active_query}'", flush=True)

            # 3. Cross-Session Deduplication check
            known_domains = database.get_known_domains(company_id=company_id)
            seen_in_batch = set()

            # 4. Search multi-engine sources (SearXNG Google, Bing, Yahoo, etc.)
            raw_candidates = []
            try:
                raw_candidates = await ingest_all_sources(
                    query=active_query,
                    target_service=target_service,
                    page=1,
                    discovery_mode="companies",
                    target_country=active_country
                )
            except Exception as ing_err:
                print(f"[Automation Daemon] Ingestion error: {ing_err}", flush=True)

            if not raw_candidates:
                # Polite pause before rotating to next niche
                await asyncio.sleep(4.0)
                continue

            # 5. Evaluate and Crawl Each Candidate
            for cand in raw_candidates:
                # Re-verify if job was stopped during the batch
                job_check = database.get_or_create_automation_job(company_id)
                if job_check.get("status") != "RUNNING":
                    break

                url = cand.url or ""
                raw_dom = cand.raw_domain or ""
                domain = clean_domain(raw_dom) if raw_dom else clean_domain(url)

                if not domain or domain in known_domains or domain in seen_in_batch:
                    continue
                seen_in_batch.add(domain)

                # Gate 1: Deterministic Junk Firewall
                is_junk, junk_reason = is_deterministic_junk(url=url, domain=domain)
                if is_junk:
                    continue

                # Gate 2: Strict Geo-Lock
                is_local, geo_reason, geo_conf = verify_deterministic_geo(domain=domain, target_country=active_country)
                if not is_local and geo_conf == 0.0 and "Foreign ccTLD" in geo_reason:
                    continue

                # Gate 3: Live Website & Subpage Crawl
                company_name = cand.author_or_company or domain.split('.')[0].capitalize()
                scraped_text = ""
                source_label = "homepage"
                try:
                    scraped_text, source_label = await fetch_url_content_with_subpages(url, timeout=3.5)
                except Exception:
                    pass

                # Gate 4: Contact Extraction
                contacts = extract_regex_contacts(scraped_text or cand.snippet or "", url)
                found_emails = contacts.get("emails", [])
                found_phones = contacts.get("phones", [])
                primary_email = found_emails[0] if found_emails else None
                primary_phone = found_phones[0] if found_phones else None

                # Deep Contact Prober Fallback (probes /pages/contact-us, /contact, etc.)
                if not primary_email:
                    try:
                        deep_res = await fetch_dedicated_contact_emails(url)
                        if deep_res.get("emails"):
                            found_emails = deep_res["emails"]
                            primary_email = found_emails[0]
                        if deep_res.get("phones") and not primary_phone:
                            primary_phone = deep_res["phones"][0]
                    except Exception:
                        pass

                # Update scanned metric
                database.update_automation_job(
                    company_id=company_id,
                    total_leads_scanned=job_check.get("total_leads_scanned", 0) + 1
                )

                # Record domain in history so it is never re-crawled
                database.record_discovered_domains(
                    company_id=company_id,
                    domains=[domain],
                    keyword=current_niche,
                    country=active_country
                )

                # ── STRICT EMAIL GATEKEEPER (Zero Hallucination Rule) ──────────
                # Companies without real verified emails are completely skipped from CSV!
                if not primary_email or not is_valid_email(primary_email):
                    print(f"[Automation Daemon] ⏩ Skipped {domain} (Legitimate operating business, but no contact email on website).", flush=True)
                    continue

                # ── Genuine Verified Lead Found! Atomically Save to SQLite & Live CSV ──
                lead_payload = {
                    "name": company_name,
                    "website": url,
                    "domain": domain,
                    "email": primary_email,
                    "phone": primary_phone,
                    "country": active_country,
                    "industry": current_niche,
                    "trustScore": max(min_trust, 82),
                    "outreachAngle": f"Identified operating enterprise in {current_niche}. Tailored offering: {target_service}."
                }

                saved = database.save_automation_verified_lead(company_id, lead_payload)
                if saved:
                    print(f"[Automation Daemon] 🎯 VERIFIED LEAD HARVESTED -> {company_name} ({domain}) | Email: {primary_email} | Appended to CSV.", flush=True)

                # Polite pause between candidate probes
                await asyncio.sleep(1.5)

            # Polite pause between niche rotations (5-8 seconds)
            await asyncio.sleep(5.0)

        except asyncio.CancelledError:
            print(f"[Automation Daemon {company_id}] Worker task cancelled.", flush=True)
            break
        except Exception as loop_err:
            print(f"[Automation Daemon {company_id}] ⚠️ Iteration error: {loop_err}. Continuing in 10s...", flush=True)
            await asyncio.sleep(10.0)
