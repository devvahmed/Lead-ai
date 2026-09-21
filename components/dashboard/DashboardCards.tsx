'use client';

import { motion, Variants } from 'framer-motion';

export interface DashboardStatsData {
  company_id?: number;
  company_name?: string;
  total_companies_found: number;
  total_clients?: number;
  total_harvested_leads?: number;
  qualified_leads: number;
  active_outreach: number;
  avg_trust_score: number;
  total_emails_generated?: number;
  automation_status?: string;
  automation_service?: string;
  automation_countries?: string;
  active_vault_name?: string;
  total_leads_scanned?: number;
  verified_emails_found?: number;
  current_niche?: string;
  recent_activity?: any[];
  weekly_chart?: any[];
}

interface StatCard {
  label: string;
  value: string;
  subvalue?: string;
  icon: string;
  trend: string;
  trendType: 'up' | 'down' | 'stable' | 'active';
  trendIcon: string;
  badge?: string;
}

const containerVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 28 } },
};

export default function DashboardCards({ stats }: { stats?: DashboardStatsData | null }) {
  const hasData = Boolean(
    stats &&
    ((stats.total_companies_found && stats.total_companies_found > 0) ||
      (stats.qualified_leads && stats.qualified_leads > 0) ||
      (stats.active_outreach && stats.active_outreach > 0))
  );

  const cards: StatCard[] = [
    {
      label: 'Total Prospects',
      value: stats ? stats.total_companies_found.toLocaleString() : '0',
      subvalue: stats && (stats.total_clients || stats.total_harvested_leads) ? 
        `${stats.total_clients || 0} CRM · ${stats.total_harvested_leads || 0} Auto-Harvested` : undefined,
      icon: 'corporate_fare',
      trend: hasData ? 'Live verified & saved leads' : 'Ready to discover prospects',
      trendType: hasData ? 'up' : 'stable',
      trendIcon: hasData ? 'trending_up' : 'info',
    },
    {
      label: 'Qualified Leads',
      value: stats ? stats.qualified_leads.toLocaleString() : '0',
      subvalue: stats && stats.verified_emails_found ? `${stats.verified_emails_found} verified emails` : undefined,
      icon: 'verified_user',
      trend: hasData ? 'Strict email & ICP verified' : 'Zero leads filtered yet',
      trendType: hasData ? 'up' : 'stable',
      trendIcon: hasData ? 'verified' : 'filter_alt',
    },
    {
      label: 'Active Outreach',
      value: stats ? stats.active_outreach.toLocaleString() : '0',
      subvalue: stats && stats.total_emails_generated ? `${stats.total_emails_generated} AI emails drafted` : undefined,
      icon: 'outgoing_mail',
      trend: hasData ? 'Campaigns in negotiation/outreach' : 'No active campaigns',
      trendType: hasData ? 'up' : 'stable',
      trendIcon: hasData ? 'send' : 'schedule_send',
    },
    {
      label: 'Average Fit Score',
      value: stats && stats.avg_trust_score > 0 ? `${stats.avg_trust_score}%` : (hasData ? 'Evaluating' : '0%'),
      subvalue: stats && stats.avg_trust_score > 0 ? 'Verified corporate score' : undefined,
      icon: 'health_and_safety',
      trend: stats && stats.avg_trust_score > 0 ? 'Dynamic multi-source rating' : 'Awaiting prospect scoring',
      trendType: stats && stats.avg_trust_score > 0 ? 'up' : 'stable',
      trendIcon: stats && stats.avg_trust_score > 0 ? 'analytics' : 'pending',
    },
  ];

  return (
    <motion.div
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {cards.map((card) => {
        const isUp = card.trendType === 'up';
        return (
          <motion.div
            key={card.label}
            variants={cardVariants}
            whileHover={{ y: -3, boxShadow: '0 12px 32px rgba(8, 71, 138, 0.08)' }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-sm relative overflow-hidden group transition-all"
          >
            {/* Top Accent Gradient on Hover */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 via-indigo-500 to-purple-600 opacity-0 group-hover:opacity-100 transition-opacity" />

            <div className="flex justify-between items-start mb-3">
              <div>
                <p className="text-[11.5px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                  {card.label}
                </p>
                <div className="flex items-baseline gap-2">
                  <motion.h3
                    className="text-[32px] font-extrabold text-slate-900 leading-none tracking-tight font-display"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    {card.value}
                  </motion.h3>
                </div>
                {card.subvalue && (
                  <p className="text-[11.5px] font-medium text-blue-600 mt-1.5">
                    {card.subvalue}
                  </p>
                )}
              </div>

              <div className="w-11 h-11 rounded-xl bg-blue-50/80 text-blue-600 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-600 group-hover:text-white transition-all shadow-sm">
                <span className="material-symbols-outlined text-[24px]">{card.icon}</span>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-1.5 text-[12px] font-medium">
              <span className={`material-symbols-outlined text-[16px] ${isUp ? 'text-emerald-600' : 'text-slate-400'}`}>
                {card.trendIcon}
              </span>
              <span className={isUp ? 'text-emerald-700 font-semibold' : 'text-slate-500'}>
                {card.trend}
              </span>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
