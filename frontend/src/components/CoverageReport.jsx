import React, { useEffect, useState } from 'react';
import { ShieldCheck, CheckCircle2, XCircle, AlertTriangle, FileSpreadsheet, RefreshCw, Search, HelpCircle, Zap, RotateCcw } from 'lucide-react';

export default function CoverageReport() {
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedControl, setSelectedControl] = useState(null);
  const [activeWhatIfFixes, setActiveWhatIfFixes] = useState([]);
  const [simulationDelta, setSimulationDelta] = useState(null);

  useEffect(() => {
    fetchScorecard();
  }, []);

  const fetchScorecard = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/nist-scorecard');
      const data = await res.json();
      setScorecard(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSimulateWhatIf = async (fixType) => {
    setLoading(true);
    try {
      const res = await fetch('/api/sandbox/simulate-fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fix_type: fixType })
      });
      const data = await res.json();
      if (data.success) {
        setActiveWhatIfFixes(data.active_fixes || []);
        setSimulationDelta(data.score_delta);
        await fetchScorecard();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRevertWhatIf = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sandbox/revert-fix', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setActiveWhatIfFixes([]);
        setSimulationDelta(null);
        await fetchScorecard();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleInspect = async (ctrlId) => {
    try {
      const res = await fetch('/api/audit/explain-control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ control_id: ctrlId })
      });
      const data = await res.json();
      setSelectedControl(data);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading && !scorecard) {
    return (
      <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center justify-center space-y-3">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
        <span>Loading NIST SP 800-171 Rev 3 Objective Scorecard...</span>
      </div>
    );
  }

  const controls = scorecard?.evaluated_controls || [];
  const filteredControls = controls.filter(c => {
    if (statusFilter === 'ALL') return true;
    return c.status === statusFilter;
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Interactive What-If Remediation Sandbox Bar */}
      <div className="glass-panel p-4 flex flex-wrap items-center justify-between gap-3 border-emerald-500/30 bg-gradient-to-r from-slate-900 via-slate-900 to-emerald-950/30">
        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold text-slate-200">Interactive What-If Sandbox:</span>
          {simulationDelta && (
            <span className="text-xs font-mono font-bold text-emerald-300 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-700">
              +{simulationDelta}% Readiness Score Boost
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleSimulateWhatIf('ENCRYPT_CUI_VOLUME')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeWhatIfFixes.includes('ENCRYPT_CUI_VOLUME')
                ? 'bg-emerald-600 text-white shadow'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
            }`}
          >
            ⚡ What-If: Volume Encryption
          </button>
          <button
            onClick={() => handleSimulateWhatIf('ENFORCE_MFA')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeWhatIfFixes.includes('ENFORCE_MFA')
                ? 'bg-cyan-600 text-white shadow'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
            }`}
          >
            ⚡ What-If: Enforce MFA
          </button>
          <button
            onClick={() => handleSimulateWhatIf('SEGMENT_GUEST_WIFI')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              activeWhatIfFixes.includes('SEGMENT_GUEST_WIFI')
                ? 'bg-purple-600 text-white shadow'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
            }`}
          >
            ⚡ What-If: Segment Wi-Fi
          </button>

          {activeWhatIfFixes.length > 0 && (
            <button
              onClick={handleRevertWhatIf}
              className="px-3 py-1.5 rounded-lg bg-rose-950 text-rose-300 border border-rose-800 text-xs font-bold transition flex items-center space-x-1"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Revert Baseline</span>
            </button>
          )}
        </div>
      </div>

      {/* Top Overview Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Compliance Readiness</span>
          <div className="text-3xl font-bold text-cyan-400">{scorecard.compliance_score_pct}%</div>
          <p className="text-xs text-slate-500">Based on active topology & CPRT objectives</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">MET Controls</span>
          <div className="text-3xl font-bold text-emerald-400">{scorecard.implemented_controls}</div>
          <p className="text-xs text-slate-500">Satisfied technical requirements</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">UNMET Gaps</span>
          <div className="text-3xl font-bold text-rose-400">{scorecard.gap_controls}</div>
          <p className="text-xs text-slate-500">Non-compliant technical findings</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Unconfirmed (Info)</span>
          <div className="text-3xl font-bold text-amber-400">{scorecard.partial_controls}</div>
          <p className="text-xs text-slate-500">Requires client assessor interview</p>
        </div>
      </div>

      {/* Control Family Breakdown */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-200 text-sm flex items-center">
            <FileSpreadsheet className="w-4 h-4 text-cyan-400 mr-2" />
            5 Core Technical Control Families Assessment
          </h3>
          <button
            onClick={fetchScorecard}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition"
            title="Refresh Scorecard"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scorecard.family_scores?.map((fam, idx) => (
            <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-200 text-xs">{fam.family}</span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${
                    fam.status === 'Good'
                      ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                      : fam.status === 'Action Needed'
                      ? 'bg-amber-950/80 text-amber-400 border-amber-800'
                      : 'bg-rose-950/80 text-rose-400 border-rose-800'
                  }`}
                >
                  {fam.status} ({fam.score}%)
                </span>
              </div>

              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    fam.score >= 70
                      ? 'bg-emerald-500'
                      : fam.score >= 40
                      ? 'bg-amber-500'
                      : 'bg-rose-500'
                  }`}
                  style={{ width: `${fam.score}%` }}
                />
              </div>

              {fam.met !== undefined && (
                <div className="flex justify-between text-[11px] text-slate-400 pt-1">
                  <span>MET: <strong className="text-emerald-400">{fam.met}</strong></span>
                  <span>UNMET: <strong className="text-rose-400">{fam.unmet}</strong></span>
                  <span>Unconfirmed: <strong className="text-amber-400">{fam.insufficient_data}</strong></span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Evaluated Controls List & Filter */}
      {controls.length > 0 && (
        <div className="glass-panel p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <h3 className="font-semibold text-slate-200 text-sm">
              Objective-Level Control Findings ({filteredControls.length})
            </h3>

            {/* Filter Tabs */}
            <div className="flex items-center space-x-2 text-xs">
              {['ALL', 'MET', 'UNMET', 'INSUFFICIENT_DATA'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-3 py-1 rounded-lg border transition font-mono ${
                    statusFilter === st
                      ? 'bg-cyan-600/30 text-cyan-300 border-cyan-500'
                      : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>

          {/* Controls Grid */}
          <div className="space-y-2.5">
            {filteredControls.map((ctrl, cIdx) => (
              <div
                key={cIdx}
                className={`p-3.5 rounded-xl border text-xs flex flex-wrap items-center justify-between gap-3 transition ${
                  ctrl.status === 'MET'
                    ? 'bg-emerald-950/15 border-emerald-800/40 hover:border-emerald-700'
                    : ctrl.status === 'UNMET'
                    ? 'bg-rose-950/15 border-rose-800/40 hover:border-rose-700'
                    : 'bg-amber-950/15 border-amber-800/40 hover:border-amber-700'
                }`}
              >
                <div className="space-y-1 max-w-[70%]">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono font-bold text-slate-100">{ctrl.control_id}</span>
                    <span className="text-slate-300 font-medium truncate">{ctrl.title}</span>
                  </div>
                  <p className="text-slate-400 text-[11px] leading-relaxed">{ctrl.finding}</p>
                </div>

                <div className="flex items-center space-x-3">
                  <span
                    className={`px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider flex items-center space-x-1 ${
                      ctrl.status === 'MET'
                        ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700'
                        : ctrl.status === 'UNMET'
                        ? 'bg-rose-900/50 text-rose-300 border border-rose-700'
                        : 'bg-amber-900/50 text-amber-300 border border-amber-700'
                    }`}
                  >
                    {ctrl.status === 'MET' && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
                    {ctrl.status === 'UNMET' && <XCircle className="w-3 h-3 text-rose-400" />}
                    {ctrl.status === 'INSUFFICIENT_DATA' && <AlertTriangle className="w-3 h-3 text-amber-400" />}
                    <span>{ctrl.status}</span>
                  </span>

                  <button
                    onClick={() => handleInspect(ctrl.control_id)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition flex items-center space-x-1 font-mono text-xs"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>Inspect</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Selected Control Detail Modal/Drawer */}
      {selectedControl && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-panel max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4 border border-cyan-500/50 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <span className="font-mono text-cyan-400 font-bold text-base">
                  NIST {selectedControl.control_id}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded text-[10px] font-bold uppercase border ${
                    selectedControl.status === 'MET'
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                      : selectedControl.status === 'UNMET'
                      ? 'bg-rose-950 text-rose-300 border-rose-800'
                      : 'bg-amber-950 text-amber-300 border-amber-800'
                  }`}
                >
                  {selectedControl.status}
                </span>
              </div>
              <button
                onClick={() => setSelectedControl(null)}
                className="text-slate-400 hover:text-white px-2.5 py-1 rounded bg-slate-800 text-xs"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-1 text-xs">
              <strong className="text-cyan-400 block">Requirement Statement:</strong>
              <p className="text-slate-300 bg-slate-900 p-3 rounded-lg border border-slate-800 leading-relaxed">
                {selectedControl.description}
              </p>
            </div>

            {selectedControl.objectives?.length > 0 && (
              <div className="space-y-1 text-xs">
                <strong className="text-amber-400 block">CPRT Determination Objectives (NIST SP 800-171A):</strong>
                <ul className="space-y-2 pl-1">
                  {selectedControl.objectives.map((obj, oIdx) => (
                    <li key={oIdx} className="p-2.5 rounded-lg bg-slate-900/80 border border-slate-800 text-slate-300 flex items-start space-x-2">
                      <span className="font-mono text-amber-400 font-bold">{oIdx + 1}.</span>
                      <span className="leading-relaxed">{obj}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="space-y-1 text-xs">
              <strong className="text-cyan-400 block">Topology Audit Finding:</strong>
              <p className="text-slate-200 bg-slate-900/90 p-3 rounded-lg border border-slate-800 leading-relaxed">
                {selectedControl.finding_explanation}
              </p>
            </div>

            {selectedControl.action_for_assessor && (
              <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 text-amber-200 text-xs space-y-1">
                <strong className="text-amber-400 block font-semibold flex items-center">
                  <HelpCircle className="w-3.5 h-3.5 mr-1" />
                  Action for Cyber Clinic Assessor (Interview Prompt):
                </strong>
                <p className="text-slate-200 leading-relaxed">{selectedControl.action_for_assessor}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

