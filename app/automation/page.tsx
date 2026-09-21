'use client';

import React, { useState, useEffect, useRef } from 'react';
import AutomationRadar3D from '@/components/automation/AutomationRadar3D';
import { getAuthToken, getSavedCompany, CompanyProfile } from '@/lib/auth';

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

interface CountryOption {
  name: string;
  code: string;
  flag: string;
  region: string;
}

const GLOBAL_COUNTRY_DATABASE: CountryOption[] = [
  // North America
  { name: 'United States', code: 'US', flag: '🇺🇸', region: 'North America' },
  { name: 'Canada', code: 'CA', flag: '🇨🇦', region: 'North America' },
  { name: 'Mexico', code: 'MX', flag: '🇲🇽', region: 'North America' },

  // Europe
  { name: 'United Kingdom', code: 'GB', flag: '🇬🇧', region: 'Europe' },
  { name: 'Germany', code: 'DE', flag: '🇩🇪', region: 'Europe' },
  { name: 'France', code: 'FR', flag: '🇫🇷', region: 'Europe' },
  { name: 'Netherlands', code: 'NL', flag: '🇳🇱', region: 'Europe' },
  { name: 'Ireland', code: 'IE', flag: '🇮🇪', region: 'Europe' },
  { name: 'Switzerland', code: 'CH', flag: '🇨🇭', region: 'Europe' },
  { name: 'Sweden', code: 'SE', flag: '🇸🇪', region: 'Europe' },
  { name: 'Norway', code: 'NO', flag: '🇳🇴', region: 'Europe' },
  { name: 'Denmark', code: 'DK', flag: '🇩🇰', region: 'Europe' },
  { name: 'Spain', code: 'ES', flag: '🇪🇸', region: 'Europe' },
  { name: 'Italy', code: 'IT', flag: '🇮🇹', region: 'Europe' },
  { name: 'Belgium', code: 'BE', flag: '🇧🇪', region: 'Europe' },
  { name: 'Austria', code: 'AT', flag: '🇦🇹', region: 'Europe' },
  { name: 'Poland', code: 'PL', flag: '🇵🇱', region: 'Europe' },
  { name: 'Finland', code: 'FI', flag: '🇫🇮', region: 'Europe' },
  { name: 'Portugal', code: 'PT', flag: '🇵🇹', region: 'Europe' },

  // Middle East & GCC
  { name: 'United Arab Emirates', code: 'AE', flag: '🇦🇪', region: 'Middle East' },
  { name: 'Saudi Arabia', code: 'SA', flag: '🇸🇦', region: 'Middle East' },
  { name: 'Qatar', code: 'QA', flag: '🇶🇦', region: 'Middle East' },
  { name: 'Kuwait', code: 'KW', flag: '🇰🇼', region: 'Middle East' },
  { name: 'Bahrain', code: 'BH', flag: '🇧🇭', region: 'Middle East' },
  { name: 'Oman', code: 'OM', flag: '🇴🇲', region: 'Middle East' },
  { name: 'Turkey', code: 'TR', flag: '🇹🇷', region: 'Middle East' },

  // Asia Pacific & South Asia
  { name: 'Pakistan', code: 'PK', flag: '🇵🇰', region: 'Asia Pacific' },
  { name: 'Australia', code: 'AU', flag: '🇦🇺', region: 'Asia Pacific' },
  { name: 'Singapore', code: 'SG', flag: '🇸🇬', region: 'Asia Pacific' },
  { name: 'New Zealand', code: 'NZ', flag: '🇳🇿', region: 'Asia Pacific' },
  { name: 'Japan', code: 'JP', flag: '🇯🇵', region: 'Asia Pacific' },
  { name: 'South Korea', code: 'KR', flag: '🇰🇷', region: 'Asia Pacific' },
  { name: 'Malaysia', code: 'MY', flag: '🇲🇾', region: 'Asia Pacific' },
  { name: 'Hong Kong', code: 'HK', flag: '🇭🇰', region: 'Asia Pacific' },
  { name: 'India', code: 'IN', flag: '🇮🇳', region: 'Asia Pacific' },
  { name: 'Indonesia', code: 'ID', flag: '🇮🇩', region: 'Asia Pacific' },
  { name: 'Philippines', code: 'PH', flag: '🇵🇭', region: 'Asia Pacific' },
  { name: 'Thailand', code: 'TH', flag: '🇹🇭', region: 'Asia Pacific' },
  { name: 'Vietnam', code: 'VN', flag: '🇻🇳', region: 'Asia Pacific' },

  // Americas & Africa
  { name: 'Brazil', code: 'BR', flag: '🇧🇷', region: 'Americas' },
  { name: 'South Africa', code: 'ZA', flag: '🇿🇦', region: 'Africa' },
  { name: 'Egypt', code: 'EG', flag: '🇪🇬', region: 'MENA' },
];

const POPULAR_QUICK_COUNTRIES = [
  'United States',
  'United Kingdom',
  'Pakistan',
  'United Arab Emirates',
  'Canada',
  'Saudi Arabia',
  'Germany',
  'Australia',
  'Singapore',
  'France',
  'Netherlands',
  'Qatar',
];

const REGIONAL_PRESETS = [
  { label: '🇺🇸 US & UK', countries: ['United States', 'United Kingdom'] },
  { label: '🌎 North America', countries: ['United States', 'Canada'] },
  { label: '🕌 GCC / Gulf', countries: ['United Arab Emirates', 'Saudi Arabia', 'Qatar'] },
  { label: '🇵🇰 Pak & Gulf', countries: ['Pakistan', 'United Arab Emirates', 'Saudi Arabia'] },
  { label: '🇪🇺 Western Europe', countries: ['United Kingdom', 'Germany', 'France', 'Netherlands'] },
  { label: '🌏 Asia Hub', countries: ['Australia', 'Singapore', 'Japan', 'Pakistan'] },
];

function getCountryFlag(name: string): string {
  const match = GLOBAL_COUNTRY_DATABASE.find(
    (c) => c.name.toLowerCase() === name.toLowerCase()
  );
  return match?.flag || '🌐';
}

const MAX_COUNTRIES = 4;
const MIN_COUNTRIES = 1;

export default function AutomationPage() {
  const [statusData, setStatusData] = useState<AutomationStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Logged-in Company Context
  const [savedCompany, setSavedCompany] = useState<CompanyProfile | null>(null);
  const [companyServicesList, setCompanyServicesList] = useState<string[]>([]);
  const [dynamicPlaceholder, setDynamicPlaceholder] = useState(
    'e.g. Custom AI Sales Assistants, ERP Solutions, Web Development...'
  );

  // Form State
  const [serviceInput, setServiceInput] = useState('');
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [minTrustScore, setMinTrustScore] = useState(70);

  // CSV Destination Decision Modal
  const [showCsvModal, setShowCsvModal] = useState(false);

  // Refs to prevent polling from overwriting user changes!
  const hasUserEditedCountriesRef = useRef(false);
  const hasUserEditedServiceRef = useRef(false);
  const initialSyncDoneRef = useRef(false);

  // Country Search & Picker State
  const [countrySearchQuery, setCountrySearchQuery] = useState('');
  const [isCountryDropdownOpen, setIsCountryDropdownOpen] = useState(false);

  // On mount: load saved company to populate dynamic placeholder
  useEffect(() => {
    const company = getSavedCompany();
    if (company) {
      setSavedCompany(company);
      if (company.services) {
        const parsed = company.services
          .split(/[,;\n]+/)
          .map((s) => s.trim())
          .filter(Boolean);
        if (parsed.length > 0) {
          setCompanyServicesList(parsed);
          setDynamicPlaceholder(`e.g. ${parsed.slice(0, 3).join(', ')}...`);
        }
      } else if (company.industry) {
        setDynamicPlaceholder(`e.g. ${company.industry} Solutions, Consulting, Automation...`);
      }
    }
  }, []);

  // Fetch status on mount and poll
  const fetchStatus = async () => {
    try {
      const token = getAuthToken();
      const res = await fetch('/api/automation/status', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data: AutomationStatusResponse = await res.json();
        setStatusData(data);

        // Helper to detect legacy 4-country default
        const isLegacyCountriesList = (list?: string[]) => {
          if (!Array.isArray(list) || list.length !== 4) return false;
          const lower = list.map((c) => c.toLowerCase());
          return (
            lower.includes('united states') &&
            lower.includes('pakistan') &&
            lower.includes('united kingdom') &&
            lower.includes('canada')
          );
        };

        const serverCountries =
          Array.isArray(data.targetCountries) && !isLegacyCountriesList(data.targetCountries)
            ? data.targetCountries
            : [];

        // ONLY on the very first mount/sync:
        if (!initialSyncDoneRef.current) {
          initialSyncDoneRef.current = true;
          if (data.targetService && !hasUserEditedServiceRef.current && !serviceInput) {
            setServiceInput(data.targetService);
          }
          if (serverCountries.length > 0 && !hasUserEditedCountriesRef.current) {
            setSelectedCountries(serverCountries);
          }
        } else if (data.status === 'RUNNING') {
          // If actively running on server, mirror the running configuration if user hasn't edited
          if (data.targetService && !hasUserEditedServiceRef.current) {
            setServiceInput(data.targetService);
          }
          if (serverCountries.length > 0 && !hasUserEditedCountriesRef.current) {
            setSelectedCountries(serverCountries);
          }
        }
        // When status is STOPPED or PAUSED: NEVER touch selectedCountries or serviceInput during polling!
        // The user has complete control to add or remove countries.
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

  const filteredCountries = GLOBAL_COUNTRY_DATABASE.filter(
    (c) =>
      c.name.toLowerCase().includes(countrySearchQuery.toLowerCase()) ||
      c.region.toLowerCase().includes(countrySearchQuery.toLowerCase())
  );

  const handleToggleCountry = (country: string) => {
    hasUserEditedCountriesRef.current = true;
    if (selectedCountries.includes(country)) {
      setErrorMsg('');
      setSelectedCountries((prev) => prev.filter((c) => c !== country));
    } else {
      if (selectedCountries.length >= MAX_COUNTRIES) {
        setErrorMsg(
          `Maximum ${MAX_COUNTRIES} countries allowed. Please remove one country before adding another.`
        );
        return;
      }
      setErrorMsg('');
      setSelectedCountries((prev) => [...prev, country]);
    }
  };

  const handleRemoveCountry = (country: string) => {
    hasUserEditedCountriesRef.current = true;
    setErrorMsg('');
    setSelectedCountries((prev) =>
      prev.filter((c) => c.toLowerCase() !== country.toLowerCase())
    );
  };

  const handleClearAllCountries = () => {
    hasUserEditedCountriesRef.current = true;
    setErrorMsg('');
    setSelectedCountries([]);
  };

  const handleAddSearchedCountry = (country: string) => {
    hasUserEditedCountriesRef.current = true;
    const clean = country.trim();
    if (!clean) return;
    if (selectedCountries.some((c) => c.toLowerCase() === clean.toLowerCase())) {
      setErrorMsg(`${clean} is already selected.`);
      return;
    }
    if (selectedCountries.length >= MAX_COUNTRIES) {
      setErrorMsg(
        `Maximum ${MAX_COUNTRIES} countries allowed. Please remove one before adding ${clean}.`
      );
      return;
    }
    setErrorMsg('');
    setSelectedCountries((prev) => [...prev, clean]);
    setCountrySearchQuery('');
    setIsCountryDropdownOpen(false);
  };

  const handleApplyPreset = (presetCountries: string[]) => {
    hasUserEditedCountriesRef.current = true;
    setErrorMsg('');
    setSelectedCountries(presetCountries.slice(0, MAX_COUNTRIES));
  };

  const handleStart = () => {
    if (!serviceInput.trim()) {
      setErrorMsg('Please specify your target service or offering before launching.');
      return;
    }
    if (selectedCountries.length === 0) {
      setErrorMsg('Please select at least 1 target country market before launching.');
      return;
    }
    setErrorMsg('');

    // Previous run parameters from database status
    const prevService = (statusData?.targetService || '').trim();
    const prevCountries = (statusData?.targetCountries || [])
      .map((c: string) => c.trim().toLowerCase())
      .sort();

    const currentService = serviceInput.trim();
    const currentCountries = [...selectedCountries]
      .map((c: string) => c.trim().toLowerCase())
      .sort();

    // Check if user changed service OR changed countries
    const serviceChanged = Boolean(
      prevService && prevService.toLowerCase() !== currentService.toLowerCase()
    );
    const countriesChanged = Boolean(
      prevCountries.length > 0 &&
      JSON.stringify(prevCountries) !== JSON.stringify(currentCountries)
    );

    // Check if previous run has any saved data / CSV
    const hasPreviousRunData = Boolean(
      (statusData?.verifiedEmailsFound || 0) > 0 ||
      (statusData?.csvFilePath && statusData.csvFilePath.length > 0)
    );

    if (hasPreviousRunData && (serviceChanged || countriesChanged)) {
      setShowCsvModal(true);
      return;
    }

    // No changes or no previous data: proceed directly with append
    executeStart('append');
  };

  const executeStart = async (csvMode: 'new' | 'append') => {
    setShowCsvModal(false);
    setActionLoading(true);
    setErrorMsg('');
    try {
      const token = getAuthToken();
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
          csv_mode: csvMode,
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
      const token = getAuthToken();
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
    const token = getAuthToken();
    window.open(`/api/automation/download-csv${token ? `?auth=${encodeURIComponent(token)}` : ''}`, '_blank');
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
            <div className="mt-1 text-xs text-emerald-400/90 truncate" title={statusData?.csvFilePath || ''}>
              {statusData?.csvFilePath
                ? `📄 ${statusData.csvFilePath.split(/[\/\\]/).pop()}`
                : '100% genuine verified emails only'}
            </div>
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
          <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-4 gap-2">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Auto-Pilot Configuration</h2>
                {savedCompany?.name && (
                  <span className="rounded-md bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
                    {savedCompany.name}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Define the services you provide and target geographic markets. The autonomous engine handles niche rotation, multi-engine scraping, and email extraction.
              </p>
            </div>
            {savedCompany?.industry && (
              <div className="text-[11px] text-slate-400 bg-slate-800/60 px-3 py-1 rounded-lg border border-slate-700/50">
                Industry: <span className="text-slate-200 font-semibold">{savedCompany.industry}</span>
              </div>
            )}
          </div>

          {errorMsg && (
            <div className="rounded-lg border border-red-500/30 bg-red-950/40 p-3 text-xs text-red-300">
              {errorMsg}
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            {/* Service Input */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Your Service / Solution Offering
                </label>
                {savedCompany?.name && (
                  <span className="text-[10px] text-emerald-400/90 font-mono">
                    Tailored to {savedCompany.name}
                  </span>
                )}
              </div>
              <input
                type="text"
                disabled={isRunning}
                value={serviceInput}
                onChange={(e) => {
                  hasUserEditedServiceRef.current = true;
                  setServiceInput(e.target.value);
                }}
                placeholder={dynamicPlaceholder}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-60"
              />

              {/* Quick Select Chips from Company Services */}
              {companyServicesList.length > 0 && (
                <div className="pt-1 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-400">
                    <span className="text-emerald-400">✦</span>
                    <span>Quick Select from Your Offerings:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {companyServicesList.map((srv, idx) => {
                      const isSelected = serviceInput.toLowerCase().trim() === srv.toLowerCase().trim();
                      return (
                        <button
                          key={idx}
                          type="button"
                          disabled={isRunning}
                          onClick={() => {
                            hasUserEditedServiceRef.current = true;
                            setServiceInput(srv);
                          }}
                          className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
                            isSelected
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/60 shadow-sm shadow-emerald-950'
                              : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80 hover:text-white border border-slate-700/60'
                          }`}
                        >
                          {srv}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

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

            {/* Dynamic Target Countries Management Deck */}
            <div className="space-y-3 md:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                    Target Geographic Markets
                  </label>
                  <p className="text-[11px] text-slate-400">
                    Select 1 to 4 countries of your choice. The autonomous harvester rotates across these markets continuously.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-mono font-bold border transition-all ${
                      selectedCountries.length >= MAX_COUNTRIES
                        ? 'bg-amber-500/10 border-amber-500/40 text-amber-400'
                        : 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'
                    }`}
                  >
                    {selectedCountries.length} / {MAX_COUNTRIES} Selected
                  </span>
                </div>
              </div>

              {/* Active Selected Countries Tags */}
              <div className="flex flex-wrap items-center gap-2 p-3 rounded-xl border border-slate-800/90 bg-slate-950/80 shadow-inner min-h-[52px]">
                <span className="text-xs font-medium text-slate-400 flex items-center gap-1 mr-1">
                  <span className="text-emerald-400">🌐</span>
                  Active Rotation:
                </span>
                {selectedCountries.length === 0 ? (
                  <span className="text-xs text-slate-500 italic py-0.5">
                    No countries selected yet. Pick 1 to 4 countries from presets below or search any country.
                  </span>
                ) : (
                  selectedCountries.map((c) => (
                    <span
                      key={c}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-3 py-1 text-xs font-semibold text-emerald-300 shadow-sm shadow-emerald-950/50"
                    >
                      <span>{getCountryFlag(c)}</span>
                      <span>{c}</span>
                      {!isRunning && (
                        <button
                          type="button"
                          onClick={() => handleRemoveCountry(c)}
                          className="ml-1 rounded p-0.5 text-emerald-400/80 hover:bg-emerald-900/60 hover:text-emerald-100 transition-colors cursor-pointer"
                          title={`Remove ${c}`}
                        >
                          ✕
                        </button>
                      )}
                    </span>
                  ))
                )}
                {!isRunning && selectedCountries.length > 0 && (
                  <button
                    type="button"
                    onClick={handleClearAllCountries}
                    className="ml-auto text-[11px] text-slate-400 hover:text-red-400 underline transition-colors cursor-pointer"
                  >
                    Clear All
                  </button>
                )}
              </div>

              {/* Search & Custom Country Picker */}
              {!isRunning && (
                <div className="relative">
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        value={countrySearchQuery}
                        onChange={(e) => {
                          setCountrySearchQuery(e.target.value);
                          setIsCountryDropdownOpen(true);
                        }}
                        onFocus={() => setIsCountryDropdownOpen(true)}
                        placeholder="🔍 Search or type any country in the world (e.g. Norway, Singapore, Japan, France, UAE...)"
                        className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-xs text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      />
                      {countrySearchQuery && (
                        <button
                          type="button"
                          onClick={() => {
                            setCountrySearchQuery('');
                            setIsCountryDropdownOpen(false);
                          }}
                          className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-white cursor-pointer"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Dropdown Menu */}
                  {isCountryDropdownOpen && countrySearchQuery.trim() && (
                    <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-y-auto rounded-xl border border-slate-700 bg-slate-900/95 p-1 shadow-2xl backdrop-blur-md">
                      {filteredCountries.length > 0 ? (
                        filteredCountries.map((c) => {
                          const isAlreadySelected = selectedCountries.includes(c.name);
                          return (
                            <button
                              key={c.code}
                              type="button"
                              onClick={() => {
                                handleToggleCountry(c.name);
                                setCountrySearchQuery('');
                                setIsCountryDropdownOpen(false);
                              }}
                              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition-colors cursor-pointer ${
                                isAlreadySelected
                                  ? 'bg-emerald-500/15 text-emerald-300'
                                  : 'text-slate-200 hover:bg-slate-800'
                              }`}
                            >
                              <span className="flex items-center gap-2">
                                <span>{c.flag}</span>
                                <span className="font-medium">{c.name}</span>
                                <span className="text-[10px] text-slate-500">({c.region})</span>
                              </span>
                              <span className="font-mono text-[11px] text-slate-400">
                                {isAlreadySelected ? '✓ Selected' : '+ Add'}
                              </span>
                            </button>
                          );
                        })
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleAddSearchedCountry(countrySearchQuery)}
                          className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs text-emerald-300 hover:bg-slate-800 transition-colors cursor-pointer"
                        >
                          <span>Add custom country: "{countrySearchQuery.trim()}"</span>
                          <span className="text-emerald-400 font-bold">+ Add</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 1-Click Regional Presets */}
              {!isRunning && (
                <div className="space-y-1.5 pt-1">
                  <div className="flex items-center gap-1 text-[11px] font-medium text-slate-400">
                    <span className="text-emerald-400">⚡</span>
                    <span>1-Click Regional Presets:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {REGIONAL_PRESETS.map((preset, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleApplyPreset(preset.countries)}
                        className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs font-medium text-slate-300 hover:border-slate-700 hover:bg-slate-800 hover:text-white transition-all cursor-pointer shadow-sm"
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Popular Global Fast-Toggles */}
              {!isRunning && (
                <div className="space-y-1.5 pt-1">
                  <div className="text-[11px] font-medium text-slate-400">
                    Popular Global Markets:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {POPULAR_QUICK_COUNTRIES.map((c) => {
                      const isSelected = selectedCountries.includes(c);
                      return (
                        <button
                          key={c}
                          type="button"
                          disabled={isRunning}
                          onClick={() => handleToggleCountry(c)}
                          className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
                            isSelected
                              ? 'border-emerald-500/50 bg-emerald-500/20 text-emerald-300 shadow-sm'
                              : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                          } disabled:opacity-60`}
                        >
                          <span>{getCountryFlag(c)}</span> {c}
                          <span className="ml-1 text-[10px] opacity-80">{isSelected ? '✓' : '+'}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
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

        {/* ─── Target Configuration Change / CSV Lead Destination Modal ─── */}
      {showCsvModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="relative w-full max-w-xl rounded-2xl border border-slate-700/80 bg-[#0c1220] p-6 shadow-2xl shadow-emerald-950/40 text-slate-100">
            {/* Top Close Button */}
            <button
              onClick={() => setShowCsvModal(false)}
              className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
            >
              ✕
            </button>

            {/* Header with Neon Icon */}
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500/20 to-teal-500/10 border border-emerald-500/40 text-2xl shadow-inner shadow-emerald-500/20">
                📁
              </div>
              <div>
                <h3 className="text-lg font-bold text-white tracking-tight">
                  Campaign Configuration Changed
                </h3>
                <p className="text-xs text-emerald-400 font-medium">
                  Choose Lead Destination / CSV File Preference
                </p>
              </div>
            </div>

            <p className="mt-3 text-xs text-slate-300 leading-relaxed">
              Aapne target <strong className="text-white">Service</strong> ya <strong className="text-white">Country Markets</strong> change ki hain. Nayi leads ko kahan save karna chahte hain?
            </p>

            {/* Comparison Box */}
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-xl border border-slate-800 bg-slate-950/70 p-3.5 text-xs">
              <div className="space-y-1 border-b sm:border-b-0 sm:border-r border-slate-800/80 pb-2.5 sm:pb-0 sm:pr-3">
                <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  <span>⏮️ Previous Campaign</span>
                </div>
                <div className="text-slate-200 font-medium truncate" title={statusData?.targetService || 'N/A'}>
                  <span className="text-slate-400">Service:</span> {statusData?.targetService || 'Previous Niche'}
                </div>
                <div className="text-slate-300 truncate" title={statusData?.targetCountries?.join(', ') || 'N/A'}>
                  <span className="text-slate-400">Markets:</span> {statusData?.targetCountries?.join(', ') || 'N/A'}
                </div>
                <div className="text-[11px] text-emerald-400 font-mono">
                  {statusData?.verifiedEmailsFound || 0} leads saved in current vault
                </div>
              </div>

              <div className="space-y-1 sm:pl-1">
                <div className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                  <span>✨ New Target</span>
                </div>
                <div className="text-emerald-300 font-semibold truncate" title={serviceInput}>
                  <span className="text-slate-400">Service:</span> {serviceInput}
                </div>
                <div className="text-slate-200 truncate" title={selectedCountries.join(', ')}>
                  <span className="text-slate-400">Markets:</span> {selectedCountries.join(', ')}
                </div>
                <div className="text-[11px] text-slate-400 font-mono">
                  Ready to stream verified leads
                </div>
              </div>
            </div>

            {/* Decision Cards */}
            <div className="mt-5 space-y-3">
              {/* Option 1: New CSV (Recommended) */}
              <button
                type="button"
                onClick={() => executeStart('new')}
                disabled={actionLoading}
                className="group w-full flex items-start gap-3.5 rounded-xl border border-emerald-500/40 bg-gradient-to-r from-emerald-950/40 to-slate-900 p-4 text-left transition-all hover:border-emerald-400 hover:shadow-lg hover:shadow-emerald-950/50 cursor-pointer"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-300 text-lg group-hover:scale-110 transition-transform">
                  🆕
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-white group-hover:text-emerald-300 transition-colors">
                      Start Fresh Dedicated CSV (Recommended)
                    </span>
                    <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/40">
                      Clean & Isolated
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-300 leading-snug">
                    Nayi campaign ke liye fresh CSV file banayein. Aapki purani leads mehfooz rahengi aur bilkul alag rahengi (no data mix-up).
                  </p>
                </div>
              </button>

              {/* Option 2: Append to Existing CSV */}
              <button
                type="button"
                onClick={() => executeStart('append')}
                disabled={actionLoading}
                className="group w-full flex items-start gap-3.5 rounded-xl border border-slate-700/80 bg-slate-900/60 p-4 text-left transition-all hover:border-slate-600 hover:bg-slate-800/80 cursor-pointer"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-300 text-lg group-hover:scale-110 transition-transform">
                  ➕
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-slate-200 group-hover:text-white transition-colors">
                      Append to Existing CSV
                    </span>
                    <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-400">
                      Combined File
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400 leading-snug">
                    Usi purani CSV file mein aage add karein. New leads purani leads ke sath ek hi file mein merge ho kar save hoti rahengi.
                  </p>
                </div>
              </button>
            </div>

            {/* Footer / Dismiss */}
            <div className="mt-5 flex justify-end gap-2 border-t border-slate-800/80 pt-3">
              <button
                type="button"
                onClick={() => setShowCsvModal(false)}
                className="rounded-xl px-4 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
              >
                Cancel / Modify Inputs
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
