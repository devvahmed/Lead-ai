'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { DashboardStatsData } from './DashboardCards';

export default function AutomationLiveBanner({ stats }: { stats?: DashboardStatsData | null }) {
  const isRunning = stats?.automation_status === 'RUNNING';
  const scanned = stats?.total_leads_scanned ?? 0;
  const verified = stats?.verified_emails_found ?? 0;
  const niche = stats?.current_niche || '';
  const service = stats?.automation_service || 'All Services';
  const vaultName = stats?.active_vault_name || '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`mb-6 rounded-2xl border p-5 transition-all relative overflow-hidden ${
        isRunning
          ? 'bg-gradient-to-r from-emerald-950 via-slate-900 to-blue-950 border-emerald-500/30 text-white shadow-lg shadow-emerald-950/20'
          : 'bg-white border-slate-200 text-slate-900 shadow-sm'
      }`}
    >
      {isRunning ? (
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3.5">
            <div className="relative flex-shrink-0 mt-0.5 sm:mt-0">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                <span className="material-symbols-outlined text-[22px] animate-pulse">radar</span>
              </div>
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
                  24/7 Autonomous Harvester Live
                </span>
                {niche && (
                  <span className="text-[11.5px] font-medium text-slate-300 bg-white/10 px-2.5 py-0.5 rounded-md">
                    Scanning Niche: <strong className="text-white">{niche}</strong>
                  </span>
                )}
              </div>
              <p className="text-[13px] text-slate-300 mt-1">
                Targeting <strong className="text-white font-semibold">{service}</strong> · Vault:{' '}
                <span className="text-emerald-400 font-mono text-[12px]">{vaultName || 'Active Leads CSV'}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap self-end lg:self-center">
            <div className="flex items-center gap-4 bg-white/5 border border-white/10 rounded-xl px-4 py-2">
              <div>
                <p className="text-[10px] uppercase font-bold text-slate-400">Scanned</p>
                <p className="text-[16px] font-bold text-white font-mono">{scanned.toLocaleString()}</p>
              </div>
              <div className="w-px h-6 bg-white/10" />
              <div>
                <p className="text-[10px] uppercase font-bold text-emerald-400">Verified Emails</p>
                <p className="text-[16px] font-bold text-emerald-400 font-mono">{verified.toLocaleString()}</p>
              </div>
            </div>

            <Link
              href="/automation"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-[13px] transition-colors shadow-sm"
            >
              <span>Live Console</span>
              <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start sm:items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center flex-shrink-0">
              <span className="material-symbols-outlined text-[22px]">smart_toy</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                  Harvester Standby
                </span>
                <span className="text-[12px] text-slate-500">Continuous Lead Finder</span>
              </div>
              <p className="text-[13.5px] font-medium text-slate-800 mt-0.5">
                Run background crawler daemons that extract verified B2B emails into dedicated CSV files.
              </p>
            </div>
          </div>

          <Link
            href="/automation"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-slate-900 hover:bg-blue-600 text-white font-semibold text-[13px] transition-all shadow-sm shrink-0 self-start sm:self-center"
          >
            <span className="material-symbols-outlined text-[16px]">bolt</span>
            <span>Configure 24/7 Harvester</span>
          </Link>
        </div>
      )}
    </motion.div>
  );
}
