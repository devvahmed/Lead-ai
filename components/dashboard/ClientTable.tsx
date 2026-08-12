'use client';

import { useState, useEffect } from 'react';
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
  search_query?: string;
}

export default function ClientTable() {
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [loading, setLoading] = useState(true);

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

  return (
    <motion.div
      className="bg-white rounded-2xl border border-gray-200/80 shadow-sm overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, type: 'spring', stiffness: 300, damping: 30 }}
    >
      {/* Header */}
      <div className="p-5 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
        <div>
          <h3 className="text-[16px] font-bold text-gray-900">Your Saved Clients & Pipeline</h3>
          <p className="text-[12px] text-gray-500 mt-0.5">Isolated multi-tenant prospect list for your company</p>
        </div>
        <Link
          href="/clients"
          className="text-blue-600 hover:text-blue-700 text-[13px] font-semibold hover:underline flex items-center gap-1"
        >
          <span>View All ({clients.length})</span>
          <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
        </Link>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        {loading ? (
          <div className="py-12 text-center text-gray-400">
            <span className="material-symbols-outlined text-3xl animate-spin text-blue-500 mb-2 block">sync</span>
            <p className="text-[13px] font-medium text-gray-600">Loading your clients...</p>
          </div>
        ) : clients.length === 0 ? (
          <div className="py-12 text-center text-gray-400 bg-gray-50/50">
            <span className="material-symbols-outlined text-4xl mb-2 text-gray-300 block">corporate_fare</span>
            <p className="text-[14px] font-semibold text-gray-700">No Saved Clients Yet</p>
            <p className="text-[12px] text-gray-400 max-w-sm mx-auto mt-1 mb-4">
              Discover prospects in the AI Discovery tool and save them to populate your company pipeline.
            </p>
            <Link
              href="/discover"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white font-semibold text-[13px] hover:bg-blue-700 transition-colors shadow-sm"
            >
              <span className="material-symbols-outlined text-[17px]">travel_explore</span>
              Discover Prospects Now
            </Link>
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/80 border-b border-gray-100">
                {['Company Name', 'Niche Keyword', 'Status', 'Fit Score', 'Country', 'Action'].map((h, i) => (
                  <th
                    key={h}
                    className={`text-[11px] font-bold uppercase tracking-wider text-gray-400 p-4 ${i === 5 ? 'text-right' : ''}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-[13.5px]">
              {clients.slice(0, 6).map((client, i) => {
                const statusStyle = client.status === 'Won'
                  ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
                  : client.status === 'In Negotiation'
                  ? 'bg-amber-100 text-amber-800 border-amber-200'
                  : client.status === 'Contacted'
                  ? 'bg-blue-100 text-blue-800 border-blue-200'
                  : client.status === 'Qualified'
                  ? 'bg-purple-100 text-purple-800 border-purple-200'
                  : 'bg-gray-100 text-gray-700 border-gray-200';

                return (
                  <motion.tr
                    key={client.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="border-b border-gray-100 hover:bg-blue-50/20 transition-colors h-[54px] group"
                  >
                    <td className="p-4 font-semibold text-gray-900">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 font-bold flex items-center justify-center text-[12px] flex-shrink-0 border border-blue-100">
                          {client.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <p className="text-[13.5px] font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                            {client.name}
                          </p>
                          <p className="text-[11px] text-gray-400 truncate max-w-[180px]">
                            {client.industry || 'General Industry'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">
                      {client.search_query ? (
                        <span className="px-2 py-0.5 rounded-md bg-purple-50 text-purple-700 border border-purple-100 text-[11px] font-semibold">
                          {client.search_query}
                        </span>
                      ) : (
                        <span className="text-[11.5px] text-gray-400 italic">General Niche</span>
                      )}
                    </td>
                    <td className="p-4">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-bold border ${statusStyle}`}>
                        {client.status}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className="w-[50px] bg-gray-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-1.5 rounded-full ${client.trust_score >= 80 ? 'bg-emerald-500' : client.trust_score >= 50 ? 'bg-blue-500' : 'bg-amber-500'}`}
                            style={{ width: `${client.trust_score || 70}%` }}
                          />
                        </div>
                        <span className="font-bold text-[12px] text-gray-700">
                          {client.trust_score || 70}%
                        </span>
                      </div>
                    </td>
                    <td className="p-4 text-gray-500 text-[12.5px]">{client.country || 'Global'}</td>
                    <td className="p-4 text-right">
                      <Link
                        href={`/clients/${client.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-blue-600 hover:text-white text-gray-700 text-[12px] font-semibold transition-all"
                      >
                        <span>Open & Email</span>
                        <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
                      </Link>
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
