'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import { getAuthToken } from '@/lib/auth';

interface ClientItem {
  id: number;
  name: string;
  industry?: string;
  country?: string;
  status: string;
  trust_score: number;
  created_at?: string;
  website?: string;
  email?: string;
  phone?: string;
  search_query?: string;
  relevance_reason?: string;
}

export default function ClientTable() {
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'verified' | 'qualified' | 'contacted'>('all');

  useEffect(() => {
    const fetchClients = async () => {
      const token = getAuthToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const res = await fetch('/api/clients', {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        if (res.ok) {
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.clients || []);
          setClients(items);
        }
      } catch (err) {
        console.error('[ClientTable Fetch Error]:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchClients();
  }, []);

  // Filtered clients based on tab and search
  const filteredClients = useMemo(() => {
    return clients.filter((client) => {
      // Tab filter
      if (activeTab === 'verified') {
        if (!client.email || !client.email.includes('@')) return false;
      } else if (activeTab === 'qualified') {
        if (client.status !== 'Qualified' && client.status !== 'Won' && client.trust_score < 80) return false;
      } else if (activeTab === 'contacted') {
        if (client.status !== 'Contacted' && client.status !== 'In Negotiation') return false;
      }

      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = client.name.toLowerCase().includes(q);
        const matchesIndustry = (client.industry || '').toLowerCase().includes(q);
        const matchesCountry = (client.country || '').toLowerCase().includes(q);
        const matchesEmail = (client.email || '').toLowerCase().includes(q);
        const matchesNiche = (client.search_query || '').toLowerCase().includes(q);
        return matchesName || matchesIndustry || matchesCountry || matchesEmail || matchesNiche;
      }

      return true;
    });
  }, [clients, activeTab, searchQuery]);

  return (
    <motion.div
      className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35, type: 'spring', stiffness: 300, damping: 28 }}
    >
      {/* Header with Title & Controls */}
      <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex flex-col md:flex-row justify-between md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-[16px] font-bold text-slate-900">Saved Prospects & Pipeline</h3>
            <span className="text-[11.5px] font-bold bg-blue-50 text-blue-700 border border-blue-200/60 px-2 py-0.5 rounded-full">
              {clients.length} Total
            </span>
          </div>
          <p className="text-[12px] text-slate-500 mt-0.5">
            Strictly isolated company prospects with verified contact details
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Search Box */}
          <div className="relative min-w-[220px]">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-slate-400">
              search
            </span>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter prospects..."
              className="w-full pl-9 pr-3 py-1.5 text-[12.5px] bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
              >
                ✕
              </button>
            )}
          </div>

          <Link
            href="/clients"
            className="text-blue-600 hover:text-blue-700 text-[13px] font-semibold flex items-center gap-1 px-3 py-1.5 rounded-xl hover:bg-blue-50 transition-colors"
          >
            <span>View All CRM</span>
            <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
          </Link>
        </div>
      </div>

      {/* Filter Tabs Bar */}
      <div className="px-5 py-2.5 bg-white border-b border-slate-100 flex items-center gap-2 overflow-x-auto text-[12.5px] font-medium text-slate-600">
        {[
          { id: 'all', label: 'All Prospects', count: clients.length },
          { id: 'verified', label: 'Verified Emails', count: clients.filter(c => c.email && c.email.includes('@')).length },
          { id: 'qualified', label: 'High Fit (80%+)', count: clients.filter(c => c.trust_score >= 80 || c.status === 'Qualified').length },
          { id: 'contacted', label: 'In Outreach', count: clients.filter(c => c.status === 'Contacted' || c.status === 'In Negotiation').length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-slate-900 text-white font-semibold shadow-sm'
                : 'hover:bg-slate-100 text-slate-600'
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                activeTab === tab.id ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="py-14 text-center text-slate-400">
            <span className="material-symbols-outlined text-3xl animate-spin text-blue-500 mb-2 block">sync</span>
            <p className="text-[13px] font-medium text-slate-600">Loading your company prospects...</p>
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="py-12 text-center text-slate-400 bg-slate-50/40">
            <span className="material-symbols-outlined text-4xl mb-2 text-slate-300 block">corporate_fare</span>
            <p className="text-[14px] font-semibold text-slate-700">
              {searchQuery ? 'No prospects match your search' : 'No prospects in this tab yet'}
            </p>
            <p className="text-[12px] text-slate-400 max-w-sm mx-auto mt-1 mb-4">
              {searchQuery
                ? 'Try adjusting your search terms or clearing the filter.'
                : 'Discover prospects with AI Discovery or the 24/7 background harvester.'}
            </p>
            <div className="flex items-center justify-center gap-3">
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="px-3.5 py-1.5 rounded-xl border border-slate-200 text-slate-600 text-[13px] font-semibold hover:bg-slate-100"
                >
                  Clear Search
                </button>
              )}
              <Link
                href="/discover"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white font-semibold text-[13px] hover:bg-blue-700 transition-colors shadow-sm"
              >
                <span className="material-symbols-outlined text-[17px]">travel_explore</span>
                Discover Prospects
              </Link>
            </div>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {['Company & Contact', 'Niche / Market', 'Status', 'Fit Score', 'Country', 'Outreach Action'].map((h, i) => (
                  <th
                    key={h}
                    className={`text-[11px] font-bold uppercase tracking-wider text-slate-400 p-4 ${i === 5 ? 'text-right' : ''}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-[13.5px] divide-y divide-slate-100">
              {filteredClients.slice(0, 8).map((client, i) => {
                const statusStyle = client.status === 'Won'
                  ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                  : client.status === 'In Negotiation'
                  ? 'bg-amber-100 text-amber-800 border-amber-200'
                  : client.status === 'Contacted'
                  ? 'bg-blue-100 text-blue-800 border-blue-200'
                  : client.status === 'Qualified'
                  ? 'bg-purple-100 text-purple-800 border-purple-200'
                  : 'bg-slate-100 text-slate-700 border-slate-200';

                const trust = client.trust_score || 0;

                return (
                  <motion.tr
                    key={client.id}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="hover:bg-blue-50/30 transition-colors group"
                  >
                    {/* Company & Email */}
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 font-bold flex items-center justify-center text-[12px] flex-shrink-0 border border-blue-100 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                          {client.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0 max-w-[240px]">
                          <p className="text-[13.5px] font-bold text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                            {client.name}
                          </p>
                          {client.email ? (
                            <p className="text-[11.5px] font-mono text-emerald-600 truncate flex items-center gap-1 mt-0.5">
                              <span className="material-symbols-outlined text-[13px]">check_circle</span>
                              {client.email}
                            </p>
                          ) : (
                            <p className="text-[11px] text-slate-400 truncate mt-0.5">
                              {client.industry || 'B2B Enterprise'}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Niche Keyword */}
                    <td className="p-4">
                      {client.search_query ? (
                        <span className="px-2.5 py-1 rounded-md bg-purple-50 text-purple-700 border border-purple-100 text-[11px] font-semibold inline-block max-w-[150px] truncate">
                          {client.search_query}
                        </span>
                      ) : (
                        <span className="text-[12px] text-slate-500 font-medium">
                          {client.industry || 'Direct ICP'}
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="p-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-bold border ${statusStyle}`}>
                        {client.status}
                      </span>
                    </td>

                    {/* Fit Score */}
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className="w-[50px] bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-1.5 rounded-full ${
                              trust >= 80 ? 'bg-emerald-500' : trust >= 50 ? 'bg-blue-500' : 'bg-amber-500'
                            }`}
                            style={{ width: `${Math.max(10, trust)}%` }}
                          />
                        </div>
                        <span className="font-bold text-[12px] text-slate-700">
                          {trust > 0 ? `${trust}%` : 'Evaluating'}
                        </span>
                      </div>
                    </td>

                    {/* Country */}
                    <td className="p-4 text-slate-600 text-[12.5px] font-medium">
                      {client.country || 'Global'}
                    </td>

                    {/* Action */}
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {client.website && (
                          <a
                            href={client.website.startsWith('http') ? client.website : `https://${client.website}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg border border-slate-200 text-slate-400 hover:text-blue-600 hover:bg-slate-50 transition-colors"
                            title="Visit Website"
                          >
                            <span className="material-symbols-outlined text-[15px]">open_in_new</span>
                          </a>
                        )}
                        <Link
                          href={`/clients/${client.id}`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-blue-600 hover:text-white text-slate-700 text-[12px] font-semibold transition-all shadow-xs"
                        >
                          <span>Draft Email</span>
                          <span className="material-symbols-outlined text-[15px]">edit_square</span>
                        </Link>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
