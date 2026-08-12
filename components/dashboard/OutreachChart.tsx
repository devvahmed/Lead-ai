'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const defaultChartData = [
  { day: 'Week 1', emails: 0, calls: 0, meetings: 0 },
  { day: 'Week 2', emails: 0, calls: 0, meetings: 0 },
  { day: 'Week 3', emails: 0, calls: 0, meetings: 0 },
  { day: 'Week 4', emails: 0, calls: 0, meetings: 0 },
];

const legend = [
  { label: 'Outreach Emails', color: '#2563eb' },
  { label: 'Calls Connected', color: '#7c3aed' },
  { label: 'Meetings Booked', color: '#10b981' },
];

export default function OutreachChart({ activeOutreach = 0, weeklyChart }: { activeOutreach?: number; weeklyChart?: any[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const hasOutreach = activeOutreach > 0 || (weeklyChart && weeklyChart.some(d => d.emails > 0));

  // Dynamic 4-week pipeline dataset
  const chartData = (weeklyChart && weeklyChart.length > 0) ? weeklyChart : defaultChartData;

  const maxVal = Math.max(...chartData.map(d => Math.max(d.emails, d.calls || 0, d.meetings || 0)), 10) + 2;

  return (
    <motion.div
      className="lg:col-span-2 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-6 flex flex-col justify-between relative overflow-hidden"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
    >
      {/* Chart Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-gray-100 pb-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-pulse" />
            <h3 className="text-[16px] font-bold text-gray-900">Outreach & Activity Timeline</h3>
          </div>
          <p className="text-[12.5px] text-gray-500 mt-0.5">
            4-Week rolling performance metrics (Emails, Calls & Meetings booked)
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 flex-wrap bg-gray-50 px-3 py-1.5 rounded-xl border border-gray-200/60">
          {legend.map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: l.color }} />
              <span className="text-[11.5px] font-medium text-gray-700">{l.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Chart Body */}
      <div className="relative flex-1 min-h-[220px] flex items-end justify-between gap-4 pt-8 px-4">
        {!hasOutreach && (
          <div className="absolute inset-0 bg-white/90 backdrop-blur-[2px] z-20 flex flex-col items-center justify-center p-6 text-center rounded-xl">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-2.5 shadow-sm">
              <span className="material-symbols-outlined text-[24px]">bar_chart</span>
            </div>
            <p className="text-[14px] font-bold text-gray-800">No Outreach Campaign Data Yet</p>
            <p className="text-[12px] text-gray-500 max-w-xs mt-1">
              Start discovering clients and drafting outreach emails to build your live analytics graph.
            </p>
          </div>
        )}

        {/* Background Grid Lines */}
        <div className="absolute inset-x-4 inset-y-8 flex flex-col justify-between pointer-events-none z-0">
          {[1, 0.75, 0.5, 0.25, 0].map((step, idx) => (
            <div key={idx} className="border-b border-gray-100 w-full flex justify-between items-center">
              <span className="text-[10px] text-gray-400 font-mono select-none">
                {Math.round(maxVal * step)}
              </span>
            </div>
          ))}
        </div>

        {/* Bars Container */}
        <div className="relative z-10 w-full flex items-end justify-around h-full pt-4">
          {chartData.map((d, i) => {
            const emailHeight = (d.emails / maxVal) * 100;
            const isHovered = hoveredIndex === i;

            return (
              <div
                key={d.day}
                onMouseEnter={() => setHoveredIndex(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                className="relative group flex flex-col items-center flex-1 max-w-[80px] h-full justify-end cursor-pointer"
              >
                {/* Floating Tooltip */}
                <AnimatePresence>
                  {isHovered && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: -8, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      className="absolute bottom-full mb-2 z-30 bg-slate-900 text-white rounded-xl p-3 shadow-xl border border-slate-700 min-w-[140px] pointer-events-none text-left"
                    >
                      <p className="text-[11.5px] font-bold text-blue-400 border-b border-slate-700 pb-1 mb-1.5">
                        {d.day} Performance
                      </p>
                      <div className="space-y-1 text-[11px]">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-gray-300 font-medium">Emails Sent:</span>
                          <span className="font-bold text-blue-400">{d.emails}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-gray-300 font-medium">Calls Connected:</span>
                          <span className="font-bold text-purple-400">{d.calls || 0}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-gray-300 font-medium">Meetings Booked:</span>
                          <span className="font-bold text-emerald-400">{d.meetings || 0}</span>
                        </div>
                      </div>
                      {/* Arrow */}
                      <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-slate-900" />
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Vertical Bar Group */}
                <div className="w-full flex items-end justify-center gap-1.5 h-[160px]">
                  {/* Emails Bar */}
                  <motion.div
                    className={`w-6 rounded-t-lg transition-all duration-300 ${
                      isHovered ? 'bg-blue-500 shadow-md shadow-blue-500/40 ring-2 ring-blue-300' : 'bg-blue-600'
                    }`}
                    initial={{ height: 0 }}
                    animate={{ height: `${Math.max(6, emailHeight)}%` }}
                    transition={{ duration: 0.5, delay: i * 0.1 }}
                  />

                  {/* Calls Bar */}
                  <motion.div
                    className={`w-3.5 rounded-t-md transition-all duration-300 ${
                      isHovered ? 'bg-purple-400 shadow-sm' : 'bg-purple-500/70'
                    }`}
                    initial={{ height: 0 }}
                    animate={{ height: `${Math.max(4, ((d.calls || 0) / maxVal) * 100)}%` }}
                    transition={{ duration: 0.5, delay: i * 0.1 + 0.05 }}
                  />

                  {/* Meetings Bar */}
                  <motion.div
                    className={`w-3.5 rounded-t-md transition-all duration-300 ${
                      isHovered ? 'bg-emerald-400 shadow-sm' : 'bg-emerald-500/70'
                    }`}
                    initial={{ height: 0 }}
                    animate={{ height: `${Math.max(3, ((d.meetings || 0) / maxVal) * 100)}%` }}
                    transition={{ duration: 0.5, delay: i * 0.1 + 0.1 }}
                  />
                </div>

                {/* X Axis Label */}
                <span className={`text-[12px] font-semibold mt-3 transition-colors ${
                  isHovered ? 'text-blue-600 font-bold' : 'text-gray-600'
                }`}>
                  {d.day}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
