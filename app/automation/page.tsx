'use client';

import React, { useState, useEffect, useRef } from 'react';
import AutomationRadar3D from '@/components/automation/AutomationRadar3D';

interface AutomationStatusResponse {
  companyId: number;
  status: 'RUNNING' | 'STOPPED' | 'PAUSED';
  isActivelyLooping: boolean;
  targetService: string;
  targetCountries: string[];
  minTrustScore: number;
  totalLeadsScanned: number;
  verifiedEmailsFound: number;
  currentNiche: string;
  currentQuery: string;
  csvFilePath: string;
  startedAt: string;
  lastHeartbeat: string;
  recentVerifiedLeads: Array<{
    id?: number;
    name: string;
    website: string;
    domain: string;
    email: string;
    phone?: string;
    country: string;
    industry: string;
    trust_score: number;
    outreach_angle: string;
    created_at: string;
  }>;
}

const AVAILABLE_COUNTRIES = [
  'United States',
  'Pakistan',
  'United Kingdom',
  'Canada',
  'Germany',
  'Australia',
  'United Arab Emirates',
  'Saudi Arabia',
];

export default function AutomationPage() {
  const [statusData, setStatusData] = useState<AutomationStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Form State
  const [serviceInput, setServiceInput] = useState('');
  const [selectedCountries, setSelectedCountries] = useState<string[]>([
    'United States',
    'Pakistan',
    'United Kingdom',
    'Canada',
  ]);
  const [minTrustScore, setMinTrustScore] = useState(70);

  // Fetch status on mount and poll
  const fetchStatus = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      const res = await fetch('/api/automation/status', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data: AutomationStatusResponse = await res.json();
        setStatusData(data);
        if (data.targetService && !serviceInput) {
          setServiceInput(data.targetService);
        }
        if (data.targetCountries && data.targetCountries.length > 0) {
          setSelectedCountries(data.targetCountries);
        }
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3500);
    return () => clearInterval(interval);
  }, []);

  const handleToggleCountry = (country: string) => {
    if (selectedCountries.includes(country)) {
      if (selectedCountries.length > 1) {
        setSelectedCountries(selectedCountries.filter((c) => c !== country));
      }
    } else {
      setSelectedCountries([...selectedCountries, country]);
    }
  };

  const handleStart = async () => {
    if (!serviceInput.trim()) {
      setErrorMsg('Please specify your target service or offering before launching.');
      return;
    }
    setErrorMsg('');
    setActionLoading(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      const res = await fetch('/api/automation/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          target_service: serviceInput.trim(),
          target_countries: selectedCountries,
          min_trust_score: minTrustScore,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Failed to start');
      }
      await fetchStatus();
    } catch (err: any) {
      setErrorMsg(err.message || 'Error starting automation');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
      await fetch('/api/automation/stop', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      await fetchStatus();
    } catch (err) {
      console.error('Stop error:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDownloadCSV = () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    window.open(`/api/automation/download-csv${token ? `?auth=${token}` : ''}`, '_blank');
  };

  const isRunning = statusData?.status === 'RUNNING';
  const lastLead = statusData?.recentVerifiedLeads?.[0]
    ? {
        name: statusData.recentVerifiedLeads[0].name,
        email: statusData.recentVerifiedLeads[0].email,
        country: statusData.recentVerifiedLeads[0].country,
      }
    : null;

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 p-6 md:p-10 font-sans">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Top Header & Live Status Pill */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">
                24/7 Autonomous Harvester
              </h1>
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-emerald-400">
                Enterprise Daemon
              </span>
            </div>
            <p className="mt-1.5 text-sm text-slate-400 max-w-2xl">
              Server-native background lead discovery. Runs 24/7 across dynamic niches, crawls genuine contact pages,
              filters fake leads, and streams strictly verified emails into a permanent live CSV.
            </p>
          </div>

          {/* Status Badge & CSV Export Button */}
          <div className="flex items-center gap-3">
            <div
              className={`flex items-center gap-2 rounded-xl border px-4 py-2 text-xs font-semibold uppercase tracking-wider shadow-lg ${
                isRunning
                  ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300 shadow-emerald-950/50'
                  : 'border-slate-800 bg-slate-900 text-slate-400'
              }`}
            >
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  isRunning ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]' : 'bg-slate-500'
                }`}
              ></span>
              {isRunning ? 'AUTO-PILOT ACTIVE (24/7)' : 'AUTO-PILOT STANDBY'}
            </div>

            <button
              onClick={handleDownloadCSV}
              className="flex items-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-600/20 px-4 py-2 text-sm font-semibold text-emerald-300 transition-all hover:bg-emerald-600 hover:text-white shadow-lg shadow-emerald-950/40 cursor-pointer"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Download Live CSV
            </button>
          </div>
        </div>

        {/* 3D Holographic Radar Component */}
        <AutomationRadar3D
          isRunning={isRunning}
          currentNiche={statusData?.currentNiche}
          currentQuery={statusData?.currentQuery}
          verifiedCount={statusData?.verifiedEmailsFound || 0}
          scannedCount={statusData?.totalLeadsScanned || 0}
          lastLead={lastLead}
        />

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Companies Scanned</div>
            <div className="mt-2 text-3xl font-extrabold text-white">
              {statusData?.totalLeadsScanned?.toLocaleString() || 0}
            </div>
            <div className="mt-1 text-xs text-slate-500">Crawled & verified against junk filters</div>
          </div>

          <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-5 shadow-lg shadow-emerald-950/20 backdrop-blur-md">
            <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400">Verified Emails in CSV</div>
            <div className="mt-2 text-3xl font-extrabold text-emerald-300">
              {statusData?.verifiedEmailsFound?.toLocaleString() || 0}
            </div>
            <div className="mt-1 text-xs text-emerald-500/80">100% genuine verified emails only</div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Exploring Niche</div>
            <div className="mt-2 text-base font-bold text-cyan-300 truncate">
              {statusData?.currentNiche || 'Dynamic Exploration'}
            </div>
            <div className="mt-1 text-xs text-slate-500 truncate">
              {statusData?.currentQuery || 'Rotating SearXNG search engines'}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-md">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">Reboot Resilience</div>
            <div className="mt-2 flex items-center gap-2 text-base font-bold text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span>
              SQLite State-Locked
            </div>
            <div className="mt-1 text-xs text-slate-500">Survives server restarts automatically</div>
          </div>
        </div>

        {/* Configuration Card & Action Controls */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl backdrop-blur-md space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-lg font-bold text-white">Auto-Pilot Configuration</h2>
              <p className="text-xs text-slate-400">
                Define the services you provide and target geographic markets. The autonomous engine handles niche rotation, multi-engine scraping, and email extraction.
              </p>
            </div>
          </div>

          {errorMsg && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300">
              {errorMsg}
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Service Input */}
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Your Service / Solution Offering
              </label>
              <input
                type="text"
                disabled={isRunning}
                value={serviceInput}
                onChange={(e) => setServiceInput(e.target.value)}
                placeholder="e.g. Custom AI Sales Assistants, ERP Solutions, Web Development..."
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-60"
              />
              <p className="text-[11px] text-slate-500">
                AI uses this offering to dynamically hypothesize and find industries with active operational bottlenecks.
              </p>
            </div>

            {/* Minimum Trust Score Threshold */}
            <div className="space-y-2">
              <div className="flex justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Minimum Trust Score Threshold
                </label>
                <span className="font-mono text-xs font-bold text-emerald-400">{minTrustScore}+</span>
              </div>
              <input
                type="range"
                min="50"
                max="95"
                step="5"
                disabled={isRunning}
                value={minTrustScore}
                onChange={(e) => setMinTrustScore(Number(e.target.value))}
                className="w-full accent-emerald-500 cursor-pointer disabled:opacity-60"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>50 (Broadest)</span>
                <span>70 (Recommended B2B)</span>
                <span>95 (Strict Enterprise)</span>
              </div>
            </div>

            {/* Target Countries Selector Chips */}
            <div className="space-y-2 md:col-span-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Target Geographic Markets (Engine auto-rotates across selected)
              </label>
              <div className="flex flex-wrap gap-2 pt-1">
                {AVAILABLE_COUNTRIES.map((c) => {
                  const isSelected = selectedCountries.includes(c);
                  return (
                    <button
                      key={c}
                      type="button"
                      disabled={isRunning}
                      onClick={() => handleToggleCountry(c)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all cursor-pointer ${
                        isSelected
                          ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300 shadow-sm'
                          : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700'
                      } disabled:opacity-60`}
                    >
                      {isSelected ? '✓ ' : '+ '}
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Action Control Buttons */}
          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-800/80 pt-4">
            {!isRunning ? (
              <button
                onClick={handleStart}
                disabled={actionLoading}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-emerald-950/50 transition-all hover:opacity-95 disabled:opacity-50 cursor-pointer"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
                {actionLoading ? 'Starting Engine...' : '🚀 Launch 24/7 Auto-Pilot'}
              </button>
            ) : (
              <button
                onClick={handleStop}
                disabled={actionLoading}
                className="flex items-center gap-2 rounded-xl border border-red-500/40 bg-red-950/40 px-6 py-2.5 text-sm font-bold text-red-300 shadow-lg shadow-red-950/40 transition-all hover:bg-red-900 hover:text-white disabled:opacity-50 cursor-pointer"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
                </svg>
                {actionLoading ? 'Stopping...' : '🛑 Stop Auto-Pilot'}
              </button>
            )}
          </div>
        </div>

        {/* Live Harvested Verified Leads Feed Table */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl backdrop-blur-md">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-lg font-bold text-white">Live Verified Leads Stream</h2>
              <p className="text-xs text-slate-400">
                Companies genuinely harvested with validated contact emails. Filtered through the Zero-Hallucination Gate.
              </p>
            </div>
            <span className="rounded-md border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs text-slate-300">
              Auto-Appended to CSV
            </span>
          </div>

          <div className="mt-4 overflow-x-auto">
            {statusData?.recentVerifiedLeads && statusData.recentVerifiedLeads.length > 0 ? (
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="border-b border-slate-800 bg-slate-950/40 text-[11px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="py-3 px-4">Company Name</th>
                    <th className="py-3 px-4">Verified Email</th>
                    <th className="py-3 px-4">Phone</th>
                    <th className="py-3 px-4">Country & Industry</th>
                    <th className="py-3 px-4">Trust Score</th>
                    <th className="py-3 px-4">Outreach Angle</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {statusData.recentVerifiedLeads.map((lead, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-sans font-semibold text-slate-100">
                        <a
                          href={lead.website}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-emerald-400 hover:underline"
                        >
                          {lead.name}
                        </a>
                      </td>
                      <td className="py-3 px-4 text-emerald-400 font-bold">
                        {lead.email}
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {lead.phone || '—'}
                      </td>
                      <td className="py-3 px-4 font-sans text-slate-300">
                        <span className="inline-block rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 mr-1.5">
                          {lead.country}
                        </span>
                        <span className="text-slate-400 text-[11px]">{lead.industry}</span>
                      </td>
                      <td className="py-3 px-4 font-bold text-emerald-400">
                        {lead.trust_score}%
                      </td>
                      <td className="py-3 px-4 font-sans text-[11px] text-slate-400 max-w-xs truncate">
                        {lead.outreach_angle || 'Direct verified business target'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="py-12 text-center text-slate-500">
                <div className="text-3xl mb-2">📡</div>
                <p className="text-sm">No verified leads collected yet in this run.</p>
                <p className="text-xs text-slate-600 mt-1">
                  Click &ldquo;Launch 24/7 Auto-Pilot&rdquo; above to start background harvesting.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
