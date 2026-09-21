'use client';

import { useState, useEffect, useCallback } from 'react';
import DashboardCards, { DashboardStatsData } from '@/components/dashboard/DashboardCards';
import AutomationLiveBanner from '@/components/dashboard/AutomationLiveBanner';
import OutreachChart from '@/components/dashboard/OutreachChart';
import ActivityFeed from '@/components/dashboard/ActivityFeed';
import ClientTable from '@/components/dashboard/ClientTable';
import { getAuthToken, getSavedCompany, CompanyProfile } from '@/lib/auth';
import Link from 'next/link';

export default function DashboardPage() {
  const [company, setCompany] = useState<CompanyProfile | null>(null);
  const [stats, setStats] = useState<DashboardStatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastSynced, setLastSynced] = useState<string>('Just now');

  const fetchStats = useCallback(async (isManual = false) => {
    const token = getAuthToken();
    if (!token) {
      setLoading(false);
      return;
    }

    if (isManual) setRefreshing(true);

    try {
      const res = await fetch('/api/dashboard-stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        cache: 'no-store',
      });

      if (res.ok) {
        const data = await res.json();
        setStats(data);
        if (data.company_name) {
          setCompany((prev) => (prev ? { ...prev, name: data.company_name } : null));
        }
        const now = new Date();
        setLastSynced(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      }
    } catch (err) {
      console.error('[Dashboard Page Fetch Error]:', err);
    } finally {
      setLoading(false);
      if (isManual) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const saved = getSavedCompany();
    if (saved) {
      setCompany(saved);
    }

    fetchStats();

    // 10-second background polling for seamless synchronization with 24/7 automation harvester
    const interval = setInterval(() => {
      fetchStats(false);
    }, 10000);

    return () => clearInterval(interval);
  }, [fetchStats]);

  return (
    <div className="p-6 pb-12 max-w-[1600px] mx-auto">
      {/* Page Header */}
      <div className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-[32px] font-extrabold text-slate-900 leading-tight tracking-tight font-display">
              Enterprise Dashboard
            </h2>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              Live Synced
            </span>
          </div>
          <p className="text-[14.5px] text-slate-500 mt-1">
            Welcome back, <span className="text-blue-600 font-bold">{company?.name || 'Partner'}</span>. 
            Here is your live pipeline and autonomous harvesting overview.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Sync Button */}
          <button
            onClick={() => fetchStats(true)}
            disabled={refreshing}
            className="px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-[13px] font-semibold flex items-center gap-1.5 shadow-xs transition-all disabled:opacity-50"
            title="Refresh dashboard stats immediately"
          >
            <span className={`material-symbols-outlined text-[17px] text-slate-500 ${refreshing ? 'animate-spin text-blue-600' : ''}`}>
              sync
            </span>
            <span className="hidden sm:inline text-xs text-slate-500">Synced {lastSynced}</span>
          </button>

          {/* 24/7 Automation Link */}
          <Link
            href="/automation"
            className="bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-xl font-semibold text-[13px] flex items-center gap-2 transition-all shadow-xs shrink-0"
          >
            <span className="material-symbols-outlined text-[17px] text-emerald-400">smart_toy</span>
            <span>24/7 Harvester</span>
          </Link>

          {/* Discover Leads CTA */}
          <Link
            href="/discover"
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl font-semibold text-[13px] flex items-center gap-2 transition-all shadow-sm shadow-blue-600/20 shrink-0"
          >
            <span className="material-symbols-outlined text-[17px]">travel_explore</span>
            <span>Discover Leads</span>
          </Link>
        </div>
      </div>

      {/* 24/7 Autonomous Harvester Live Widget Banner */}
      <AutomationLiveBanner stats={stats} />

      {/* Dynamic Stat Cards */}
      <DashboardCards stats={stats} />

      {/* Chart + Feed Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <OutreachChart activeOutreach={stats?.active_outreach || 0} weeklyChart={stats?.weekly_chart} />
        <ActivityFeed activities={(stats as any)?.recent_activity || []} />
      </div>

      {/* Clients & Prospect Table */}
      <ClientTable />
    </div>
  );
}
