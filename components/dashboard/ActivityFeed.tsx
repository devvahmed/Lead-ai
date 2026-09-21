'use client';

import { motion } from 'framer-motion';

export interface ActivityItem {
  title?: string;
  subtitle?: string;
  timestamp?: string;
  icon?: string;
  type?: string;
  company_name?: string;
  contact_email?: string;
  sent_at?: string;
  probability_score?: number;
  suggested_action?: string;
}

function formatRelativeTime(tsStr?: string): string {
  if (!tsStr) return 'Recently';
  try {
    const d = new Date(tsStr.includes('T') ? tsStr : tsStr.replace(' ', 'T') + 'Z');
    if (isNaN(d.getTime())) return 'Recently';
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

export default function ActivityFeed({ activities = [] }: { activities?: ActivityItem[] }) {
  const hasItems = Boolean(activities && activities.length > 0);

  return (
    <motion.div
      className="bg-white rounded-2xl border border-slate-200/80 shadow-sm flex flex-col min-h-[380px] overflow-hidden"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25, type: 'spring', stiffness: 300, damping: 28 }}
    >
      {/* Header */}
      <div className="p-4 px-5 border-b border-slate-100 bg-slate-50/60 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-slate-700 text-[18px]">stream</span>
          <h3 className="text-[15px] font-bold text-slate-900">Live Activity Stream</h3>
        </div>
        {hasItems && (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200/60 px-2 py-0.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live Sync
          </span>
        )}
      </div>

      {/* List Content */}
      <div className="p-4 overflow-y-auto flex-1 flex flex-col justify-start max-h-[380px] divide-y divide-slate-100">
        {!hasItems ? (
          <div className="text-center py-12 px-4 flex flex-col items-center justify-center my-auto">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 mb-2.5">
              <span className="material-symbols-outlined text-[24px]">history</span>
            </div>
            <p className="text-[13.5px] font-bold text-slate-700 mb-1">No activity logged yet</p>
            <p className="text-[12px] text-slate-400 max-w-[220px]">
              Discovered companies, automated harvester leads, and email drafts appear here in real time.
            </p>
          </div>
        ) : (
          activities.map((item, i) => {
            const displayTitle = item.title || item.company_name || 'Prospect Discovered';
            const displaySubtitle = item.subtitle || item.suggested_action || 'Lead identified';
            const isAuto = item.type === 'automation';
            const isOutreach = item.type === 'outreach';
            const isSaved = item.type === 'saved';

            const iconName = item.icon || (isAuto ? 'mark_email_read' : isOutreach ? 'auto_awesome' : 'corporate_fare');

            const badgeColor = isAuto
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : isOutreach
              ? 'bg-blue-50 text-blue-700 border-blue-200'
              : isSaved
              ? 'bg-purple-50 text-purple-700 border-purple-200'
              : 'bg-slate-100 text-slate-700 border-slate-200';

            return (
              <div
                key={i}
                className="py-3 px-1.5 flex items-start gap-3 hover:bg-slate-50/80 rounded-xl transition-colors group"
              >
                <div
                  className={`w-8 h-8 rounded-xl border flex items-center justify-center flex-shrink-0 mt-0.5 ${badgeColor}`}
                >
                  <span className="material-symbols-outlined text-[16px]">{iconName}</span>
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[13px] font-bold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                      {displayTitle}
                    </p>
                    <span className="text-[10.5px] font-medium text-slate-400 shrink-0">
                      {formatRelativeTime(item.timestamp || item.sent_at)}
                    </span>
                  </div>

                  <p className="text-[11.5px] text-slate-500 truncate mt-0.5">
                    {displaySubtitle}
                  </p>

                  {item.probability_score && item.probability_score > 0 ? (
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200/50 px-1.5 py-0.5 rounded">
                        Fit Score: {item.probability_score}%
                      </span>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
