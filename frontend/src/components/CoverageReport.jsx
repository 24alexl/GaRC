import React, { useEffect, useState } from 'react';
import { ShieldCheck, AlertOctagon, CheckCircle2, FileSpreadsheet, RefreshCw } from 'lucide-react';

export default function CoverageReport() {
  const [scorecard, setScorecard] = useState(null);
  const [loading, setLoading] = useState(true);

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

  if (loading) {
    return (
      <div className="p-8 text-center text-slate-400 text-sm">
        Loading NIST 800-171 Scorecard...
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Compliance Readiness</span>
          <div className="text-3xl font-bold text-cyan-400">{scorecard.compliance_score_pct}%</div>
          <p className="text-xs text-slate-500">Based on active topology graph</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Implemented Controls</span>
          <div className="text-3xl font-bold text-emerald-400">{scorecard.implemented_controls}</div>
          <p className="text-xs text-slate-500">Out of 110 total controls</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Partial Mitigations</span>
          <div className="text-3xl font-bold text-amber-400">{scorecard.partial_controls}</div>
          <p className="text-xs text-slate-500">Requires configuration update</p>
        </div>

        <div className="glass-panel p-5 space-y-1">
          <span className="text-xs text-slate-400 font-medium">Critical Gaps</span>
          <div className="text-3xl font-bold text-rose-400">{scorecard.gap_controls}</div>
          <p className="text-xs text-slate-500">Unaddressed requirements</p>
        </div>
      </div>

      {/* Control Family Breakdown Table */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-slate-200 text-sm flex items-center">
            <FileSpreadsheet className="w-4 h-4 text-cyan-400 mr-2" />
            NIST SP 800-171 Control Families Assessment
          </h3>
          <button
            onClick={fetchScorecard}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-400 hover:text-slate-200 transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-3">
          {scorecard.family_scores.map((fam, idx) => (
            <div key={idx} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between">
              <div className="space-y-1">
                <span className="font-medium text-slate-200 text-sm">{fam.family}</span>
                <div className="w-48 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${
                      fam.score >= 70
                        ? 'bg-emerald-500'
                        : fam.score >= 50
                        ? 'bg-amber-500'
                        : 'bg-rose-500'
                    }`}
                    style={{ width: `${fam.score}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <span className="font-mono text-sm text-slate-300">{fam.score}%</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${
                    fam.status === 'Good'
                      ? 'bg-emerald-950/80 text-emerald-400 border-emerald-800'
                      : fam.status === 'Action Needed'
                      ? 'bg-amber-950/80 text-amber-400 border-amber-800'
                      : 'bg-rose-950/80 text-rose-400 border-rose-800'
                  }`}
                >
                  {fam.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
