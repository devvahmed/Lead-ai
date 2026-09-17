'use client';

import React, { useEffect, useRef } from 'react';

interface AutomationRadar3DProps {
  isRunning: boolean;
  currentNiche?: string;
  currentQuery?: string;
  verifiedCount: number;
  scannedCount: number;
  lastLead?: {
    name: string;
    email: string;
    country: string;
  } | null;
}

interface Node3D {
  x: number;
  y: number;
  z: number;
  name: string;
  email?: string;
  status: 'scanning' | 'verified' | 'harvested';
  age: number;
  angle: number;
  lat: number;
  lon: number;
}

interface Particle3D {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  life: number;
  maxLife: number;
  color: string;
}

export default function AutomationRadar3D({
  isRunning,
  currentNiche,
  currentQuery,
  verifiedCount,
  scannedCount,
  lastLead,
}: AutomationRadar3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rotRef = useRef<{ x: number; y: number }>({ x: 0.2, y: 0 });
  const isDraggingRef = useRef(false);
  const mousePosRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 700);
    let height = (canvas.height = 420);

    const handleResize = () => {
      if (!canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = 420;
    };
    window.addEventListener('resize', handleResize);

    // Initial 3D node points around a virtual sphere
    const sphereRadius = 130;
    const nodes: Node3D[] = [];
    const sampleNames = ['Apex Global', 'Zenith D2C', 'Vanguard Retail', 'Nordic Wave', 'Aura Labs', 'Nova Health', 'Pulse Media', 'Lumen Trade'];

    for (let i = 0; i < 24; i++) {
      const lat = (Math.random() - 0.5) * Math.PI;
      const lon = Math.random() * Math.PI * 2;
      nodes.push({
        x: sphereRadius * Math.cos(lat) * Math.cos(lon),
        y: sphereRadius * Math.sin(lat),
        z: sphereRadius * Math.cos(lat) * Math.sin(lon),
        lat,
        lon,
        name: sampleNames[i % sampleNames.length],
        status: Math.random() > 0.4 ? 'verified' : 'scanning',
        age: Math.random() * 100,
        angle: Math.random() * Math.PI * 2,
      });
    }

    const particles: Particle3D[] = [];
    let radarSweep = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Cybernetic Background Glow
      const bgGrad = ctx.createRadialGradient(width / 2, height / 2, 20, width / 2, height / 2, width / 1.5);
      bgGrad.addColorStop(0, 'rgba(16, 185, 129, 0.08)');
      bgGrad.addColorStop(0.4, 'rgba(6, 182, 212, 0.04)');
      bgGrad.addColorStop(1, 'rgba(10, 15, 30, 0)');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      // Auto Rotation
      if (isRunning) {
        rotRef.current.y += 0.008;
        radarSweep += 0.035;
      } else {
        rotRef.current.y += 0.002;
      }

      const cx = width / 2;
      const cy = height / 2 - 15;
      const ry = rotRef.current.y;
      const rx = rotRef.current.x;

      // Draw 3D Globe Rings (Latitude & Longitude)
      ctx.save();
      ctx.lineWidth = 1;
      const ringSteps = 6;
      for (let r = 0; r < ringSteps; r++) {
        const phi = (r / ringSteps) * Math.PI - Math.PI / 2;
        const rad = sphereRadius * Math.cos(phi);
        const yOffset = sphereRadius * Math.sin(phi);

        ctx.beginPath();
        ctx.strokeStyle = isRunning
          ? `rgba(6, 182, 212, ${0.12 + Math.abs(Math.sin(radarSweep + r)) * 0.15})`
          : 'rgba(75, 85, 99, 0.15)';

        for (let a = 0; a <= Math.PI * 2; a += 0.2) {
          const px = rad * Math.cos(a);
          const pz = rad * Math.sin(a);

          // Rotate around Y
          const x1 = px * Math.cos(ry) + pz * Math.sin(ry);
          const z1 = -px * Math.sin(ry) + pz * Math.cos(ry);

          // Rotate around X
          const y2 = yOffset * Math.cos(rx) - z1 * Math.sin(rx);
          const z2 = yOffset * Math.sin(rx) + z1 * Math.cos(rx);

          const scale = 360 / (360 + z2);
          const sx = cx + x1 * scale;
          const sy = cy + y2 * scale;

          if (a === 0) ctx.moveTo(sx, sy);
          else ctx.lineTo(sx, sy);
        }
        ctx.stroke();
      }

      // Draw Radar Sweep Cone in 3D
      if (isRunning) {
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        const sweepX = Math.cos(radarSweep) * (sphereRadius * 1.25);
        const sweepZ = Math.sin(radarSweep) * (sphereRadius * 1.25);
        const sweepSx = cx + (sweepX * Math.cos(ry) + sweepZ * Math.sin(ry));
        const sweepSy = cy + (-sweepX * Math.sin(ry) + sweepZ * Math.cos(ry)) * Math.sin(rx);

        const sweepGrad = ctx.createLinearGradient(cx, cy, sweepSx, sweepSy);
        sweepGrad.addColorStop(0, 'rgba(16, 185, 129, 0.45)');
        sweepGrad.addColorStop(1, 'rgba(6, 182, 212, 0)');
        ctx.fillStyle = sweepGrad;
        ctx.arc(cx, cy, sphereRadius * 1.15, radarSweep - 0.35, radarSweep);
        ctx.fill();
      }

      // Project & Draw Nodes
      nodes.forEach((node, idx) => {
        node.age += 1;
        // 3D coordinates based on lat/lon
        const px = sphereRadius * Math.cos(node.lat) * Math.cos(node.lon);
        const py = sphereRadius * Math.sin(node.lat);
        const pz = sphereRadius * Math.cos(node.lat) * Math.sin(node.lon);

        // Rotation
        const x1 = px * Math.cos(ry) + pz * Math.sin(ry);
        const z1 = -px * Math.sin(ry) + pz * Math.cos(ry);
        const y2 = py * Math.cos(rx) - z1 * Math.sin(rx);
        const z2 = py * Math.sin(rx) + z1 * Math.cos(rx);

        const scale = 360 / (360 + z2);
        const sx = cx + x1 * scale;
        const sy = cy + y2 * scale;

        // Depth fog / transparency
        const alpha = Math.max(0.15, (z2 + sphereRadius) / (sphereRadius * 2));

        if (z2 > -sphereRadius * 0.8) {
          // Node dot
          ctx.beginPath();
          ctx.arc(sx, sy, isRunning ? 3.5 * scale : 2.5 * scale, 0, Math.PI * 2);

          const isVerified = node.status === 'verified';
          ctx.fillStyle = isVerified
            ? `rgba(16, 185, 129, ${alpha})`
            : `rgba(6, 182, 212, ${alpha * 0.8})`;
          ctx.shadowColor = isVerified ? '#10b981' : '#06b6d4';
          ctx.shadowBlur = isRunning ? 10 : 2;
          ctx.fill();
          ctx.shadowBlur = 0;

          // Scanning beacon pulse
          if (isRunning && idx % 3 === 0) {
            const pulse = (node.age % 40) / 40;
            ctx.beginPath();
            ctx.arc(sx, sy, 14 * pulse * scale, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(16, 185, 129, ${alpha * (1 - pulse)})`;
            ctx.lineWidth = 1.2;
            ctx.stroke();
          }

          // Laser transmission to CSV Vault
          if (isRunning && isVerified && (node.age % 120 < 40)) {
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            const targetVaultX = cx;
            const targetVaultY = height - 40;
            ctx.quadraticCurveTo(cx + x1 * 0.5, cy + 60, targetVaultX, targetVaultY);
            ctx.strokeStyle = 'rgba(16, 185, 129, 0.4)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([4, 4]);
            ctx.stroke();
            ctx.setLineDash([]);

            // Spawn vault particles
            if (Math.random() > 0.6) {
              particles.push({
                x: sx,
                y: sy,
                z: 0,
                vx: (targetVaultX - sx) * 0.035,
                vy: (targetVaultY - sy) * 0.035,
                vz: 0,
                life: 0,
                maxLife: 28,
                color: '#10b981',
              });
            }
          }
        }
      });

      // Update & Draw Flowing Data Particles
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.life += 1;
        p.x += p.vx;
        p.y += p.vy;

        const pAlpha = 1 - p.life / p.maxLife;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(16, 185, 129, ${pAlpha})`;
        ctx.shadowColor = '#10b981';
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;

        if (p.life >= p.maxLife) {
          particles.splice(i, 1);
        }
      }

      // Draw 3D CSV Vault Reservoir at bottom
      const vaultX = cx;
      const vaultY = height - 35;
      ctx.save();
      ctx.translate(vaultX, vaultY);

      // Base Platform
      ctx.beginPath();
      ctx.ellipse(0, 0, 110, 22, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.strokeStyle = isRunning ? '#10b981' : '#475569';
      ctx.lineWidth = 1.5;
      ctx.shadowColor = isRunning ? '#10b981' : '#000';
      ctx.shadowBlur = isRunning ? 15 : 0;
      ctx.fill();
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Vault Core Ring
      ctx.beginPath();
      ctx.ellipse(0, -6, 85, 16, 0, 0, Math.PI * 2);
      ctx.strokeStyle = isRunning ? 'rgba(6, 182, 212, 0.7)' : 'rgba(100, 116, 139, 0.3)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Vault Label & Live Metric
      ctx.fillStyle = '#f8fafc';
      ctx.font = '600 11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(isRunning ? 'LIVE CSV VAULT (AUTO-SYNCING)' : 'CSV VAULT (STANDBY)', 0, 4);

      ctx.restore();
      ctx.restore();

      animFrameId = requestAnimationFrame(render);
    };

    animFrameId = requestAnimationFrame(render);

    // Interactive mouse rotation handlers
    const handleMouseDown = (e: MouseEvent) => {
      isDraggingRef.current = true;
      mousePosRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const dx = e.clientX - mousePosRef.current.x;
      const dy = e.clientY - mousePosRef.current.y;
      rotRef.current.y += dx * 0.006;
      rotRef.current.x = Math.max(-0.6, Math.min(0.6, rotRef.current.x + dy * 0.006));
      mousePosRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
    };

    canvas.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('resize', handleResize);
      canvas.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      cancelAnimationFrame(animFrameId);
    };
  }, [isRunning, verifiedCount]);

  return (
    <div className="relative w-full rounded-2xl border border-slate-800 bg-slate-950/80 p-5 shadow-2xl backdrop-blur-xl overflow-hidden">
      {/* Top HUD Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3.5 w-3.5 items-center justify-center">
            {isRunning ? (
              <>
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_#10b981]"></span>
              </>
            ) : (
              <span className="h-2.5 w-2.5 rounded-full bg-slate-500"></span>
            )}
          </div>
          <div>
            <h3 className="text-sm font-semibold tracking-wider text-slate-200 uppercase">
              Autonomous Lead Radar 3D
            </h3>
            <p className="text-xs text-slate-400">
              {isRunning
                ? `Scanning: ${currentNiche || 'Dynamic Niche Discovery'}`
                : 'Auto-pilot paused. Ready to launch.'}
            </p>
          </div>
        </div>

        {/* Real-Time Telemetry Badges */}
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 font-mono text-cyan-400">
            Scanned: <strong className="text-cyan-200">{scannedCount}</strong>
          </span>
          <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 font-mono text-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.2)]">
            Verified In CSV: <strong className="text-emerald-200">{verifiedCount}</strong>
          </span>
        </div>
      </div>

      {/* 3D Canvas Canvas */}
      <div className="relative mt-2 cursor-grab active:cursor-grabbing">
        <canvas ref={canvasRef} className="block w-full" />

        {/* Floating Holographic Telemetry Cards */}
        {isRunning && (
          <>
            <div className="pointer-events-none absolute top-4 left-4 rounded-lg border border-slate-700/60 bg-slate-900/80 p-2.5 text-[11px] backdrop-blur-md">
              <div className="text-slate-400">CURRENT TARGET QUERY</div>
              <div className="font-mono text-xs font-semibold text-emerald-400 truncate max-w-[260px]">
                {currentQuery || 'Rotating SearXNG multi-engine queries...'}
              </div>
            </div>

            {lastLead && (
              <div className="pointer-events-none absolute top-4 right-4 rounded-lg border border-emerald-500/40 bg-emerald-950/40 p-2.5 text-[11px] backdrop-blur-md shadow-lg shadow-emerald-950/50">
                <div className="flex items-center gap-1.5 font-semibold text-emerald-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                  LATEST VERIFIED HARVEST
                </div>
                <div className="mt-0.5 font-medium text-slate-200">{lastLead.name}</div>
                <div className="font-mono text-[10px] text-emerald-400">{lastLead.email}</div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Hint */}
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
        <span>✦ Interactive 3D Canvas: Click and drag to rotate global radar in space</span>
        <span>Zero-Hallucination Gate: Only crawls with verified emails are persisted</span>
      </div>
    </div>
  );
}
