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

        {/* Workflow Stepper Navigation */}
        <div className="flex items-center space-x-2 mb-6 border-b border-slate-800/80 pb-3 overflow-x-auto text-sm font-medium">
          {/* Step 1: Network Topology */}
          <button
            onClick={() => setActiveTab('engine2')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'engine2'
                ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-lg shadow-purple-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-slate-800'
            }`}
          >
            <span className="w-5 h-5 rounded-full bg-purple-950 text-purple-300 border border-purple-800 text-xs flex items-center justify-center font-bold font-mono">1</span>
            <Network className="w-4 h-4" />
            <span>Network Topology</span>
          </button>

          <span className="text-slate-600 font-bold px-1">→</span>

          {/* Step 2: Compliance Assistant */}
          <button
            onClick={() => setActiveTab('engine1')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'engine1'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-lg shadow-cyan-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-slate-800'
            }`}
          >
            <span className="w-5 h-5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800 text-xs flex items-center justify-center font-bold font-mono">2</span>
            <Cpu className="w-4 h-4" />
            <span>Compliance Assistant (GraphRAG)</span>
          </button>

          <span className="text-slate-600 font-bold px-1">→</span>

          {/* Step 3: Gap Scorecard */}
          <button
            onClick={() => setActiveTab('scorecard')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition ${
              activeTab === 'scorecard'
                ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-950/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-slate-800'
            }`}
          >
            <span className="w-5 h-5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs flex items-center justify-center font-bold font-mono">3</span>
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
