import React, { useEffect, useState } from 'react';
import { Shield, Cpu, Database, Award, RefreshCw } from 'lucide-react';

export default function Header() {
  const [status, setStatus] = useState({ healthy: false, dbConnected: false, provider: 'gemini' });

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => {
        setStatus({
          healthy: data.status === 'healthy',
          dbConnected: data.db_connected,
          provider: data.llm_provider
        });
      })
      .catch(() => {});
  }, []);

  const handleSeed = async () => {
    try {
      const res = await fetch('/api/seed', { method: 'POST' });
      const data = await res.json();
      alert(`Knowledge Graph Seeded! Controls loaded: ${data.count}`);
    } catch (err) {
      alert('Failed to seed Knowledge Graph.');
    }
  };

  return (
    <header className="glass-panel mb-6 px-6 py-4 flex flex-wrap items-center justify-between border-b border-slate-800">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 to-purple-600 p-0.5 flex items-center justify-center glow-cyan">
          <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
            <Shield className="w-5 h-5 text-cyan-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="font-bold text-lg text-slate-100 tracking-tight">GaRC</h1>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
              GraphRAG XAI
            </span>
          </div>
          <p className="text-xs text-slate-400">
            OUPI Cyber Clinic Contest 2026 • Category 2 Submission
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* LLM Indicator */}
        <div className="flex items-center space-x-1.5 text-xs text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-slate-400">LLM:</span>
          <span className="font-mono text-cyan-300 capitalize">{status.provider}</span>
        </div>

        {/* Database Status Indicator */}
        <div className="flex items-center space-x-1.5 text-xs text-slate-300 bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
          <Database className="w-3.5 h-3.5 text-purple-400" />
          <span className="text-slate-400">Neo4j:</span>
          <span className={`font-medium ${status.dbConnected ? 'text-emerald-400' : 'text-amber-400'}`}>
            {status.dbConnected ? 'Active Container' : 'In-Memory Fallback'}
          </span>
        </div>

        {/* Re-seed Button */}
        <button
          onClick={handleSeed}
          className="flex items-center space-x-1 text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          title="Reload NIST 800-171 Knowledge Graph"
        >
          <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
          <span>Reload Seed KG</span>
        </button>
      </div>
    </header>
  );
}
