import React, { useState, useEffect } from 'react';
import { ShieldCheck, Cpu, Play, Search, AlertTriangle, CheckCircle, HelpCircle, XCircle, ChevronDown, ChevronRight, FileText } from 'lucide-react';
import GraphVisualizer from './GraphVisualizer';

export default function Engine1Chat() {
  const [loading, setLoading] = useState(false);
  const [auditResult, setAuditResult] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedControlDetail, setSelectedControlDetail] = useState(null);
  const [expandedFamilies, setExpandedFamilies] = useState({
    "03.01": true,
    "03.05": true,
    "03.08": true,
    "03.13": true,
    "03.14": true
  });
  const [highlightedControlId, setHighlightedControlId] = useState(null);

  useEffect(() => {
    // Automatically trigger evaluation if active topology exists
    handleRunAudit();
  }, []);

  const handleRunAudit = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/audit/evaluate-topology', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      setAuditResult(data);
    } catch (err) {
      console.error("Error executing parallel 5-family audit:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleInspectControl = async (controlId) => {
    setHighlightedControlId(controlId);
    try {
      const res = await fetch('/api/audit/explain-control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ control_id: controlId })
      });
      const data = await res.json();
      setSelectedControlDetail(data);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleFamily = (famCode) => {
    setExpandedFamilies(prev => ({
      ...prev,
      [famCode]: !prev[famCode]
    }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-140px)]">
      {/* Left Column: 5-Family Objective Audit Results */}
      <div className="lg:col-span-7 flex flex-col glass-panel p-4 h-full">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h2 className="font-semibold text-slate-200">Step 2: 5-Family Technical Compliance Audit</h2>
          </div>
          <button
            onClick={handleRunAudit}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white text-xs font-medium transition shadow-lg shadow-cyan-950/50"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{loading ? 'Auditing 5 Families...' : 'Run Parallel Audit'}</span>
          </button>
        </div>

        {/* Audit Metrics Banner */}
        {auditResult && (
          <div className="grid grid-cols-4 gap-2 my-3 p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs">
            <div className="text-center">
              <span className="text-slate-400 block text-[10px]">Readiness</span>
              <span className="font-bold text-cyan-400 text-sm">{auditResult.overall_score_pct}%</span>
            </div>
            <div className="text-center">
              <span className="text-slate-400 block text-[10px]">MET</span>
              <span className="font-bold text-emerald-400 text-sm">{auditResult.met_count} Controls</span>
            </div>
            <div className="text-center">
              <span className="text-slate-400 block text-[10px]">UNMET</span>
              <span className="font-bold text-rose-400 text-sm">{auditResult.unmet_count} Gaps</span>
            </div>
            <div className="text-center">
              <span className="text-slate-400 block text-[10px]">Unconfirmed</span>
              <span className="font-bold text-amber-400 text-sm">{auditResult.insufficient_data_count} Info</span>
            </div>
          </div>
        )}

        {/* Family Cards Accordion */}
        <div className="flex-1 overflow-y-auto space-y-3 pr-2">
          {loading && !auditResult && (
            <div className="flex flex-col items-center justify-center h-48 space-y-3 text-slate-400 text-sm">
              <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              <span>Executing concurrent 5-family objective-level audit...</span>
            </div>
          )}

          {auditResult?.family_scorecards?.map((fam, idx) => (
            <div key={idx} className="rounded-xl bg-slate-900/80 border border-slate-800 overflow-hidden transition">
              {/* Family Header */}
              <div
                onClick={() => toggleFamily(fam.family_code)}
                className="p-3 flex items-center justify-between cursor-pointer hover:bg-slate-800/60 select-none"
              >
                <div className="flex items-center space-x-2">
                  {expandedFamilies[fam.family_code] ? (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400" />
                  )}
                  <span className="font-mono text-cyan-400 font-semibold text-xs">
                    {fam.short_code} ({fam.family_code})
                  </span>
                  <span className="text-xs text-slate-200 font-medium">{fam.family_name}</span>
                </div>

                <div className="flex items-center space-x-2 text-xs">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px]">
                    {fam.met}/{fam.total} MET
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-medium border ${
                      fam.status === 'Good'
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : fam.status === 'Action Needed'
                        ? 'bg-amber-950 text-amber-300 border-amber-800'
                        : 'bg-rose-950 text-rose-300 border-rose-800'
                    }`}
                  >
                    {fam.status}
                  </span>
                </div>
              </div>

              {/* Controls List for this Family */}
              {expandedFamilies[fam.family_code] && (
                <div className="p-3 pt-0 space-y-2 border-t border-slate-800/60 mt-1">
                  {auditResult.evaluated_controls
                    ?.filter(c => c.control_id.startsWith(fam.family_code))
                    .map((ctrl, cIdx) => (
                      <div
                        key={cIdx}
                        className={`p-3 rounded-lg border text-xs space-y-2 transition ${
                          ctrl.status === 'MET'
                            ? 'bg-emerald-950/20 border-emerald-800/40 hover:border-emerald-700'
                            : ctrl.status === 'UNMET'
                            ? 'bg-rose-950/20 border-rose-800/50 hover:border-rose-700'
                            : 'bg-amber-950/20 border-amber-800/40 hover:border-amber-700'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="font-mono font-bold text-slate-200">{ctrl.control_id}</span>
                            <span className="text-slate-300 font-medium truncate max-w-[280px]">{ctrl.title}</span>
                          </div>

                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1 ${
                                ctrl.status === 'MET'
                                  ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700'
                                  : ctrl.status === 'UNMET'
                                  ? 'bg-rose-900/60 text-rose-300 border border-rose-700'
                                  : 'bg-amber-900/60 text-amber-300 border border-amber-700'
                              }`}
                            >
                              {ctrl.status === 'MET' && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                              {ctrl.status === 'UNMET' && <XCircle className="w-3 h-3 text-rose-400" />}
                              {ctrl.status === 'INSUFFICIENT_DATA' && <AlertTriangle className="w-3 h-3 text-amber-400" />}
                              <span>{ctrl.status}</span>
                            </span>

                            <button
                              onClick={() => handleInspectControl(ctrl.control_id)}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition flex items-center space-x-1 text-[11px]"
                            >
                              <Search className="w-3 h-3" />
                              <span>Trace</span>
                            </button>
                          </div>
                        </div>

                        <p className="text-slate-300 leading-relaxed">{ctrl.finding}</p>

                        {ctrl.action_for_assessor && (
                          <div className="p-2 rounded bg-slate-950/70 border border-slate-800/80 text-[11px] text-amber-300 flex items-start space-x-1.5">
                            <HelpCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                            <span><strong>Action for Assessor:</strong> {ctrl.action_for_assessor}</span>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Right Column: Visualizer & Inspect Finding Drawer */}
      <div className="lg:col-span-5 glass-panel p-4 flex flex-col space-y-3 h-full">
        <div className="flex items-center justify-between shrink-0">
          <h3 className="text-sm font-semibold text-slate-200">
            Interactive Audit Reasoning Graph
          </h3>
          {highlightedControlId && (
            <button
              onClick={() => {
                setHighlightedControlId(null);
                setSelectedControlDetail(null);
              }}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Reset Focus
            </button>
          )}
        </div>

        {/* Cytoscape Graph Canvas */}
        <div className="h-[310px] shrink-0">
          <GraphVisualizer
            graphData={auditResult?.cytoscape_graph || { nodes: [], edges: [] }}
            onNodeSelect={setSelectedNode}
            highlightControlId={highlightedControlId}
          />
        </div>

        {/* Detailed Inspection Drawer */}
        <div className="flex-1 overflow-y-auto min-h-[260px] pr-1">
          {selectedControlDetail ? (
            <div className="p-4 rounded-xl bg-slate-900/90 border border-cyan-500/60 shadow-xl space-y-3 text-xs animate-in fade-in slide-in-from-bottom-2">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-cyan-300 font-bold text-sm">
                    {selectedControlDetail.label || `NIST ${selectedControlDetail.control_id}`}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${
                      selectedControlDetail.status === 'MET'
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : selectedControlDetail.status === 'UNMET'
                        ? 'bg-rose-950 text-rose-300 border-rose-800'
                        : 'bg-amber-950 text-amber-300 border-amber-800'
                    }`}
                  >
                    {selectedControlDetail.status}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedControlDetail(null)}
                  className="text-slate-400 hover:text-white text-xs px-2 py-0.5 rounded bg-slate-800"
                >
                  ✕ Close
                </button>
              </div>

              {selectedControlDetail.parent_control && (
                <div className="text-[11px] text-slate-400">
                  <span>Parent Control: </span>
                  <strong className="text-cyan-300 font-mono">NIST {selectedControlDetail.parent_control}</strong>
                </div>
              )}

              <div>
                <strong className="text-cyan-400 block mb-1">
                  {selectedControlDetail.type === 'objective' ? 'CPRT Determination Objective:' : 'Requirement Statement:'}
                </strong>
                <p className="text-slate-300 bg-slate-950/60 p-2.5 rounded border border-slate-800 leading-relaxed">
                  {selectedControlDetail.description}
                </p>
              </div>

              {selectedControlDetail.objectives?.length > 0 && (
                <div>
                  <strong className="text-amber-400 block mb-1">CPRT Determination Objectives (800-171A):</strong>
                  <ul className="space-y-1.5 pl-1">
                    {selectedControlDetail.objectives.map((obj, oIdx) => (
                      <li key={oIdx} className="p-2 rounded bg-slate-950/40 border border-slate-800/60 text-slate-300 flex items-start space-x-2">
                        <span className="font-mono text-amber-400 font-semibold">{oIdx + 1}.</span>
                        <span className="leading-relaxed">{obj}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <strong className="text-cyan-400 block mb-1">Audit Finding:</strong>
                <p className="text-slate-200 leading-relaxed">{selectedControlDetail.finding_explanation || selectedControlDetail.finding || selectedControlDetail.detail}</p>
              </div>

              {selectedControlDetail.action_for_assessor && (
                <div className="p-3 rounded bg-amber-950/40 border border-amber-800/80 text-amber-200 space-y-1">
                  <strong className="text-amber-400 block font-semibold">Action for Cyber Clinic Assessor:</strong>
                  <p className="text-slate-200 leading-relaxed">{selectedControlDetail.action_for_assessor}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 text-center text-xs text-slate-400">
              <div>
                <div className="text-cyan-400 font-semibold mb-1 text-sm">🔍 Objective-Level Trace & Details</div>
                <p className="max-w-xs text-slate-400">
                  Click on any control card's <span className="text-cyan-300 font-mono">[Trace]</span> button or graph node to inspect its exact CPRT assessment objectives.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

