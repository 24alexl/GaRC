import React, { useState } from 'react';
import { Network, AlertTriangle, CheckCircle, Database, HelpCircle, ArrowRight, ShieldAlert, MessageSquare, Zap, RotateCcw, Send } from 'lucide-react';
import { marked } from 'marked';
import GraphVisualizer from './GraphVisualizer';

export default function Engine2Topology() {
  const [inputMode, setInputMode] = useState('copilot'); // 'copilot' | 'prompt'
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [parseResult, setParseResult] = useState(null);
  const [commitStatus, setCommitStatus] = useState(null);
  const [activeWhatIfFixes, setActiveWhatIfFixes] = useState([]);
  const [simulationDelta, setSimulationDelta] = useState(null);

  // Copilot Chat State
  const [copilotMessages, setCopilotMessages] = useState([
    {
      role: 'assistant',
      content: "### Welcome to GaRC Cyber Clinic Copilot!\n\nI'm your guided cybersecurity and **NIST SP 800-171 Rev 3** compliance assistant.\n\n- **Ask compliance questions**: *'What is CUI?'*, *'How do we enforce MFA?'*, or *'How can we segment guest Wi-Fi?'*\n- **Describe your computers & gear**: *'We have 5 laptops and a Synology NAS with client contracts'*\n- **Trace directly to CPRT**: Every control and node discussed links directly into the Knowledge Graph below!",
      kg_traces: [
        { id: "03.01.01", label: "03.01.01 Access Control", type: "control", family: "03.01", status: "ACTIVE" },
        { id: "03.05.03", label: "03.05.03 Multi-Factor Auth", type: "control", family: "03.05", status: "ACTIVE" },
        { id: "03.13.01", label: "03.13.01 Boundary Protection", type: "control", family: "03.13", status: "ACTIVE" }
      ]
    }
  ]);
  const [copilotInput, setCopilotInput] = useState('');
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotFollowups, setCopilotFollowups] = useState([
    "What is CUI and does my company have it?",
    "We have 4 Windows PCs and a Synology NAS with patient records",
    "How do I isolate Guest Wi-Fi from our office data?"
  ]);

  const sampleDescriptions = [
    "We have 10 Windows 11 workstations connected to a Synology NAS via a 1Gbps switch. The NAS stores payroll contracts and CUI.",
    "Our remote sales team uses MacBook Pro laptops connecting over OpenVPN to an AWS EC2 Linux server running PostgreSQL.",
    "Small accounting office with 5 PCs on 192.168.1.0/24 connected to an unmanaged NETGEAR router with guest Wi-Fi enabled."
  ];

  const [topoStep, setTopoStep] = useState('');

  const handleResetCopilotChat = () => {
    setCopilotMessages([
      {
        role: 'assistant',
        content: `### GaRC Cyber Clinic Copilot Ready\n\nI have active visibility into your network map (${parseResult?.nodes?.length || 0} assets loaded).\n\n- Click **'Inspect Active Network Map'** to analyze your architecture.\n- Ask questions about **NIST SP 800-171 Rev 3**, **CUI**, **MFA**, or **VLANs**.\n- Tell me about hardware you'd like to add or update.`,
        kg_traces: [
          { id: "03.01.01", label: "03.01.01 Access Control", type: "control", family: "03.01", status: "ACTIVE" },
          { id: "03.05.03", label: "03.05.03 Multi-Factor Auth", type: "control", family: "03.05", status: "ACTIVE" },
          { id: "03.13.01", label: "03.13.01 Boundary Protection", type: "control", family: "03.13", status: "ACTIVE" }
        ]
      }
    ]);
  };

  const handleSendCopilot = async (msgToSend) => {
    const text = msgToSend || copilotInput;
    if (!text.trim() || copilotLoading) return;

    const newHistory = [...copilotMessages, { role: 'user', content: text }];
    setCopilotMessages(newHistory);
    setCopilotInput('');
    setCopilotLoading(true);

    try {
      const res = await fetch('/api/chat/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: newHistory.slice(-6),
          current_nodes: parseResult?.nodes || [],
          current_edges: parseResult?.edges || []
        })
      });
      const data = await res.json();
      setCopilotMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply,
        actions_taken: data.actions_taken,
        kg_traces: data.kg_traces || []
      }]);
      if (data.suggested_followups?.length > 0) {
        setCopilotFollowups(data.suggested_followups);
      }
      if (data.topology_updated && data.topology) {
        setParseResult(data.topology);
      }
    } catch (e) {
      console.error(e);
      setCopilotMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Failed to connect to Copilot service. Please try again.'
      }]);
    } finally {
      setCopilotLoading(false);
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
        setParseResult(data.topology);
        setActiveWhatIfFixes(data.active_fixes || []);
        setSimulationDelta(data.score_delta);
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
        setParseResult(data.topology);
        setActiveWhatIfFixes([]);
        setSimulationDelta(null);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleParse = async (textToParse) => {
    const targetText = textToParse || inputText;
    if (!targetText.trim() || loading) return;

    setLoading(true);
    setCommitStatus(null);
    setTopoStep('⚡ Extracting network entities & subnets...');

    // Artificial delay for smooth UX progress banner
    await new Promise(r => setTimeout(r, 450));

    try {
      const res = await fetch('/api/engine2/parse-topology', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: targetText })
      });
      
      setTopoStep('🛡️ Evaluating MFA & CUI security attributes...');
      await new Promise(r => setTimeout(r, 450));
      
      const data = await res.json();
      setParseResult(data);
    } catch (err) {
      alert('Error parsing network topology.');
    } finally {
      setLoading(false);
      setTopoStep('');
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

        {/* Mode Toggle: Guided Copilot Chat vs Rigid Prompt Box */}
        <div className="flex items-center gap-2 pt-3 pb-2 border-b border-slate-800/80">
          <button
            onClick={() => setInputMode('copilot')}
            className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 ${
              inputMode === 'copilot'
                ? 'bg-purple-600/30 text-purple-300 border border-purple-500/50 shadow'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>💬 Copilot Chat (Guided)</span>
          </button>
          <button
            onClick={() => setInputMode('prompt')}
            className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold transition flex items-center justify-center gap-1.5 ${
              inputMode === 'prompt'
                ? 'bg-purple-600/30 text-purple-300 border border-purple-500/50 shadow'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Text Prompt (Direct)</span>
          </button>
        </div>

        {/* MODE A: Guided Cyber Clinic Copilot Chat */}
        {inputMode === 'copilot' && (
          <div className="flex-1 flex flex-col pt-3 overflow-hidden">
            {/* Active Network Map Visibility Status Bar */}
            <div className="flex items-center justify-between bg-purple-950/40 border border-purple-800/50 px-2.5 py-1.5 rounded-lg mb-2">
              <div className="flex items-center gap-1.5 text-[11px] text-purple-200">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>
                  <strong>Map Visibility:</strong> Seeing <strong>{parseResult?.nodes?.length || 0} assets</strong>
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => handleSendCopilot("Inspect my current network map and tell me what you see")}
                  disabled={copilotLoading}
                  className="text-[10px] font-semibold bg-purple-600 hover:bg-purple-500 text-white px-2 py-0.5 rounded transition shadow"
                  title="Ask Copilot to analyze your active network topology"
                >
                  🔍 Inspect Map
                </button>
                <button
                  onClick={handleResetCopilotChat}
                  className="text-[10px] text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded transition"
                  title="Clear chat"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 max-h-[320px]">
              {copilotMessages.map((msg, mIdx) => (
                <div
                  key={mIdx}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-[90%] rounded-xl p-3 text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-purple-700/80 text-white rounded-br-none shadow'
                        : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none shadow-sm'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <div
                        className="text-xs leading-relaxed font-sans space-y-1"
                        dangerouslySetInnerHTML={{
                          __html: typeof marked !== 'undefined' ? marked.parse(msg.content || '') : msg.content
                        }}
                      />
                    ) : (
                      <div className="whitespace-pre-wrap font-sans text-xs">
                        {msg.content}
                      </div>
                    )}

                    {/* CPRT Knowledge Graph Traces */}
                    {msg.kg_traces?.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-slate-800/80">
                        <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                          <span>🔗 CPRT Knowledge Graph Traces:</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {msg.kg_traces.map((tr, tIdx) => (
                            <span
                              key={tIdx}
                              className={`px-1.5 py-0.5 rounded text-[9px] font-medium border flex items-center gap-1 ${
                                tr.type === 'control'
                                  ? 'bg-purple-950/80 border-purple-800 text-purple-300'
                                  : 'bg-cyan-950/80 border-cyan-800 text-cyan-300'
                              }`}
                            >
                              <span>{tr.type === 'control' ? '🛡️' : '🖥️'}</span>
                              <span>{tr.label || tr.id}</span>
                              {tr.status && (
                                <span className={`text-[7px] px-1 py-0.2 rounded font-mono ${
                                  tr.status === 'MET' ? 'bg-emerald-900 text-emerald-300' :
                                  tr.status === 'UNMET' ? 'bg-rose-900 text-rose-300' :
                                  'bg-amber-900 text-amber-300'
                                }`}>
                                  {tr.status}
                                </span>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {msg.actions_taken?.length > 0 && (
                      <div className="mt-2 pt-1.5 border-t border-slate-800 space-y-1">
                        {msg.actions_taken.map((act, aIdx) => (
                          <div key={aIdx} className="flex items-center gap-1 text-[10px] text-emerald-400 font-mono">
                            <span>✓</span>
                            <span>{act}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <span className="text-[9px] text-slate-500 mt-0.5 px-1">
                    {msg.role === 'user' ? 'You' : 'GaRC Copilot'}
                  </span>
                </div>
              ))}
              {copilotLoading && (
                <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800 text-purple-300 text-xs animate-pulse w-fit">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>
                  <span>Reasoning & validating graph...</span>
                </div>
              )}
            </div>

            {/* Quick Suggestions */}
            {copilotFollowups?.length > 0 && (
              <div className="pt-2 pb-1 shrink-0 flex flex-wrap gap-1.5">
                {copilotFollowups.map((q, qIdx) => (
                  <button
                    key={qIdx}
                    onClick={() => handleSendCopilot(q)}
                    className="text-[10px] bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-purple-500/50 text-slate-300 hover:text-purple-200 px-2 py-1 rounded-md transition text-left truncate max-w-full"
                  >
                    💡 {q}
                  </button>
                ))}
              </div>
            )}

            {/* Chat Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendCopilot();
              }}
              className="flex items-center gap-1.5 pt-2 border-t border-slate-800 shrink-0"
            >
              <input
                type="text"
                value={copilotInput}
                onChange={(e) => setCopilotInput(e.target.value)}
                placeholder="Ask a question or describe equipment (e.g. 'We added 4 PCs & a Synology NAS')..."
                disabled={copilotLoading}
                className="flex-1 bg-slate-900 border border-slate-800 focus:border-purple-500 text-slate-100 text-xs px-3 py-2 rounded-lg outline-none transition"
              />
              <button
                type="submit"
                disabled={copilotLoading || !copilotInput.trim()}
                className="px-3.5 py-2 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition shadow flex items-center gap-1 shrink-0"
              >
                <span>Send</span>
              </button>
            </form>
          </div>
        )}

        {/* MODE B: Direct Natural Language Prompt */}
        {inputMode === 'prompt' && (
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
              <span>{loading ? 'Analyzing Network Topology...' : 'Generate Rigid Topology Draft'}</span>
              {!loading && <ArrowRight className="w-4 h-4" />}
            </button>
            
            {loading && topoStep && (
              <div className="p-3 rounded-lg bg-purple-950/70 border border-purple-800 text-purple-300 text-xs flex items-center space-x-2 animate-pulse">
                <div className="w-2 h-2 rounded-full bg-purple-400 animate-ping shrink-0" />
                <span className="font-mono font-medium">{topoStep}</span>
              </div>
            )}
          </div>
        )}


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
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-slate-200">
            Interactive Network Graph Canvas
          </h3>
          <span className="text-xs text-slate-400">Cytoscape.js Node Render</span>
        </div>

        {/* What-If Sandbox Bar */}
        <div className="flex flex-wrap items-center justify-between p-2 rounded-lg bg-slate-900/90 border border-slate-800 mb-2 gap-1.5 shrink-0">
          <div className="flex items-center gap-1.5 text-xs text-slate-300">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span className="font-semibold text-[11px]">What-If Sandbox:</span>
            {simulationDelta && (
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950 px-1.5 py-0.2 rounded border border-emerald-800">
                +{simulationDelta}% Score Boost
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => handleSimulateWhatIf('ENCRYPT_CUI_VOLUME')}
              disabled={loading}
              className={`px-2 py-0.5 rounded border text-[10px] font-medium transition ${
                activeWhatIfFixes.includes('ENCRYPT_CUI_VOLUME')
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                  : 'bg-slate-800 hover:bg-emerald-950 text-slate-300 hover:text-emerald-300 border-slate-700'
              }`}
            >
              + Encryption
            </button>
            <button
              onClick={() => handleSimulateWhatIf('ENFORCE_MFA')}
              disabled={loading}
              className={`px-2 py-0.5 rounded border text-[10px] font-medium transition ${
                activeWhatIfFixes.includes('ENFORCE_MFA')
                  ? 'bg-cyan-950 text-cyan-300 border-cyan-700'
                  : 'bg-slate-800 hover:bg-cyan-950 text-slate-300 hover:text-cyan-300 border-slate-700'
              }`}
            >
              + MFA
            </button>
            <button
              onClick={() => handleSimulateWhatIf('SEGMENT_GUEST_WIFI')}
              disabled={loading}
              className={`px-2 py-0.5 rounded border text-[10px] font-medium transition ${
                activeWhatIfFixes.includes('SEGMENT_GUEST_WIFI')
                  ? 'bg-purple-950 text-purple-300 border-purple-700'
                  : 'bg-slate-800 hover:bg-purple-950 text-slate-300 hover:text-purple-300 border-slate-700'
              }`}
            >
              + Segment Wi-Fi
            </button>
            {activeWhatIfFixes.length > 0 && (
              <button
                onClick={handleRevertWhatIf}
                disabled={loading}
                className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px] font-bold transition flex items-center gap-1"
                title="Revert What-If fixes"
              >
                <RotateCcw className="w-2.5 h-2.5" />
                <span>Revert</span>
              </button>
            )}
          </div>
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
