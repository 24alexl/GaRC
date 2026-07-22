import React, { useState } from 'react';
import Header from './components/Header';
import Engine1Chat from './components/Engine1Chat';
import Engine2Topology from './components/Engine2Topology';
import CoverageReport from './components/CoverageReport';
import { Cpu, Network, ShieldCheck } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('engine1');

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 p-4 md:p-6 font-sans">
      <div className="max-w-[1600px] mx-auto">
        <Header />

        {/* Tab Navigation */}
        <div className="flex items-center space-x-2 mb-6 border-b border-slate-800/80 pb-2">
          <button
            onClick={() => setActiveTab('engine1')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'engine1'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Cpu className="w-4 h-4" />
            <span>Engine 1: XAI GraphRAG Chat</span>
          </button>

          <button
            onClick={() => setActiveTab('engine2')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'engine2'
                ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-lg shadow-purple-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <Network className="w-4 h-4" />
            <span>Engine 2: NL Topology & Clarifications</span>
          </button>

          <button
            onClick={() => setActiveTab('scorecard')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              activeTab === 'scorecard'
                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>NIST 800-171 Gap Scorecard</span>
          </button>
        </div>

        {/* Tab Content */}
        <main>
          {activeTab === 'engine1' && <Engine1Chat />}
          {activeTab === 'engine2' && <Engine2Topology />}
          {activeTab === 'scorecard' && <CoverageReport />}
        </main>
      </div>
    </div>
  );
}
