import React, { useState } from 'react';
import { Network, AlertTriangle, CheckCircle, Database, HelpCircle, ArrowRight, ShieldAlert } from 'lucide-react';
import GraphVisualizer from './GraphVisualizer';

export default function Engine2Topology() {
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [parseResult, setParseResult] = useState(null);
  const [commitStatus, setCommitStatus] = useState(null);

  const sampleDescriptions = [
    "We have 10 Windows 11 workstations connected to a Synology NAS via a 1Gbps switch. The NAS stores payroll contracts and CUI.",
    "Our remote sales team uses MacBook Pro laptops connecting over OpenVPN to an AWS EC2 Linux server running PostgreSQL.",
    "Small accounting office with 5 PCs on 192.168.1.0/24 connected to an unmanaged NETGEAR router with guest Wi-Fi enabled."
  ];

  const handleParse = async (textToParse) => {
    const targetText = textToParse || inputText;
    if (!targetText.trim() || loading) return;

    setLoading(true);
    setCommitStatus(null);

    try {
      const res = await fetch('/api/engine2/parse-topology', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: targetText })
      });
      const data = await res.json();
      setParseResult(data);
    } catch (err) {
      alert('Error parsing network topology.');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!parseResult) return;
    setLoading(true);
    try {
      const res = await fetch('/api/engine2/commit-topology', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: parseResult.nodes,
          edges: parseResult.edges
        })
      });
      const data = await res.json();
      setCommitStatus('Topology successfully committed to Neo4j graph database!');
    } catch (err) {
      setCommitStatus('Error committing topology to database.');
    } finally {
      setLoading(false);
    }
  };

  const updateNodeProperty = (nodeId, propName, value) => {
    if (!parseResult) return;
    const updatedNodes = parseResult.nodes.map(n => {
      if (n.id === nodeId) {
        return { ...n, [propName]: value, confidence: 1.0 };
      }
      return n;
    });

    const updatedPrompts = parseResult.clarification_prompts.filter(p => p.node_id !== nodeId);

    setParseResult(prev => ({
      ...prev,
      nodes: updatedNodes,
      clarification_prompts: updatedPrompts,
      requires_clarification: updatedPrompts.length > 0
    }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-140px)]">
      {/* Left Input & Clarification Panel */}
      <div className="lg:col-span-6 flex flex-col glass-panel p-4 h-full overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Network className="w-5 h-5 text-purple-400" />
            <h2 className="font-semibold text-slate-200">Engine 2: Natural Language Topology Builder</h2>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-full bg-purple-950/80 text-purple-400 border border-purple-800">
            NL-to-Cypher Translator
          </span>
        </div>

        {/* Input Text Area */}
        <div className="py-4 space-y-3">
          <label className="text-xs font-medium text-slate-300">
            Describe your organization's network setup, devices, servers, or storage:
          </label>
          <textarea
            rows={4}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="e.g., We have 8 Windows PCs on 192.168.1.0/24 connected to an office router and a local NAS storing CUI..."
            className="w-full bg-slate-900 border border-slate-800 focus:border-purple-500 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-500 outline-none transition resize-none"
          />

          {/* Quick Presets */}
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="text-slate-500">Preset topologies:</span>
            {sampleDescriptions.map((sd, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setInputText(sd);
                  handleParse(sd);
                }}
                className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-purple-300 transition text-left truncate max-w-[220px]"
              >
                Preset {idx + 1}
              </button>
            ))}
          </div>

          <button
            onClick={() => handleParse()}
            disabled={loading || !inputText.trim()}
            className="w-full py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition flex items-center justify-center space-x-2"
          >
            <span>Generate Rigid Topology Draft</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

        {/* Clarification Prompts Section */}
        {parseResult && parseResult.clarification_prompts?.length > 0 && (
          <div className="mt-4 p-4 rounded-xl bg-amber-950/40 border border-amber-800/60 space-y-3">
            <div className="flex items-center space-x-2 text-amber-400 text-sm font-semibold">
              <AlertTriangle className="w-4 h-4" />
              <span>Clarification Required (Low Confidence Attributes)</span>
            </div>
            <p className="text-xs text-slate-300">
              GaRC identified ambiguous network properties. Select options to increase topology precision:
            </p>

            <div className="space-y-3">
              {parseResult.clarification_prompts.map((cp, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                  <p className="text-xs font-medium text-slate-200 flex items-center">
                    <HelpCircle className="w-3.5 h-3.5 text-amber-400 mr-1.5" />
                    {cp.question}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {cp.suggested_options.map((opt, oIdx) => (
                      <button
                        key={oIdx}
                        onClick={() => {
                          const isTrue = opt.toLowerCase().includes('yes');
                          updateNodeProperty(cp.node_id, cp.property_in_question, isTrue);
                        }}
                        className="text-xs px-3 py-1.5 rounded bg-slate-800 hover:bg-amber-900/60 text-slate-200 hover:text-amber-200 border border-slate-700 transition"
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Parsed Node & Edge Table */}
        {parseResult && (
          <div className="mt-4 flex-1 space-y-3 border-t border-slate-800 pt-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">
                Extracted Entities ({parseResult.nodes.length} Nodes, {parseResult.edges.length} Edges)
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                Overall Confidence: {(parseResult.confidence_score * 100).toFixed(0)}%
              </span>
            </div>

            <div className="space-y-2 text-xs">
              {parseResult.nodes.map((node, idx) => (
                <div key={idx} className="flex items-center justify-between p-2.5 rounded bg-slate-900 border border-slate-800">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-purple-300">{node.name}</span>
                    <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] uppercase">{node.type}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {node.stores_cui && (
                      <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px]">
                        CUI Asset
                      </span>
                    )}
                    {node.has_firewall_or_mfa && (
                      <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px]">
                        MFA / FW Confirmed
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Commit to Neo4j Button */}
            <div className="pt-2">
              <button
                onClick={handleCommit}
                disabled={loading}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition flex items-center justify-center space-x-2"
              >
                <Database className="w-4 h-4" />
                <span>Persist Approved Topology to Neo4j Database</span>
              </button>
              {commitStatus && (
                <p className="mt-2 text-xs text-emerald-400 text-center">{commitStatus}</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Right Canvas Column */}
      <div className="lg:col-span-6 glass-panel p-4 h-full flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-200">
            Interactive Network Graph Canvas
          </h3>
          <span className="text-xs text-slate-400">Cytoscape.js Node Render</span>
        </div>

        <div className="flex-1">
          <GraphVisualizer
            graphData={parseResult?.cytoscape_graph || { nodes: [], edges: [] }}
          />
        </div>
      </div>
    </div>
  );
}
