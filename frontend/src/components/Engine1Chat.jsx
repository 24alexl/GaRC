import React, { useState } from 'react';
import { Send, Bot, User, ShieldCheck, Cpu, Search } from 'lucide-react';
import { marked } from 'marked';
import GraphVisualizer from './GraphVisualizer';

export default function Engine1Chat() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: 'bot',
      text: "Welcome to **GaRC Engine 1 (GraphRAG Compliance Assistant)**.\n\nI am preloaded with the official **NIST SP 800-171 Rev 3 CPRT Knowledge Graph**.\n\nAsk me how to protect CUI, implement MFA, configure firewalls, or meet access control objectives!",
      graph: null,
      citedControls: []
    }
  ]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [activeGraph, setActiveGraph] = useState(null);
  const [highlightedControlId, setHighlightedControlId] = useState(null);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userText = query;
    setQuery('');
    setMessages(prev => [...prev, { sender: 'user', text: userText }]);
    setLoading(true);

    try {
      const res = await fetch('/api/engine1/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userText })
      });
      const data = await res.json();

      setMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: data.markdown_response,
          graph: data.graph,
          citedControls: data.cited_controls
        }
      ]);
      if (data.graph) {
        setActiveGraph(data.graph);
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { sender: 'bot', text: '⚠️ Connection error reaching Engine 1 API.' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-140px)]">
      {/* Left Chat Column */}
      <div className="lg:col-span-7 flex flex-col glass-panel p-4 h-full">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h2 className="font-semibold text-slate-200">Engine 1: XAI GraphRAG Assistant</h2>
          </div>
          <span className="text-xs px-2.5 py-1 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800 font-mono">
            NIST SP 800-171 Rev 3 CPRT
          </span>
        </div>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto space-y-4 py-4 pr-2">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex space-x-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.sender === 'bot' && (
                <div className="w-8 h-8 rounded-lg bg-cyan-950 border border-cyan-700 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-cyan-400" />
                </div>
              )}
              <div
                className={`max-w-[85%] rounded-xl p-4 text-sm ${
                  msg.sender === 'user'
                    ? 'bg-cyan-600 text-white rounded-br-none'
                    : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none space-y-2'
                }`}
              >
                <div
                  className="prose-custom"
                  dangerouslySetInnerHTML={{ __html: marked.parse(msg.text) }}
                />

                {msg.citedControls?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800 flex flex-wrap gap-2 items-center text-xs">
                    <span className="text-slate-400 font-medium flex items-center">
                      <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 mr-1" /> Interactive XAI Traces:
                    </span>
                    {msg.citedControls.map((ctrlId, cIdx) => (
                      <button
                        key={cIdx}
                        onClick={() => {
                          if (msg.graph) setActiveGraph(msg.graph);
                          setHighlightedControlId(ctrlId);
                        }}
                        className="px-2.5 py-1 rounded bg-amber-950/80 hover:bg-amber-900 text-amber-300 border border-amber-700/80 transition flex items-center space-x-1 font-mono"
                      >
                        <Search className="w-3 h-3 text-amber-400" />
                        <span>Trace {ctrlId}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                  <User className="w-4 h-4 text-slate-300" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex space-x-3 items-center text-slate-400 text-xs py-2">
              <Bot className="w-4 h-4 text-cyan-400 animate-spin" />
              <span>Traversing NIST 800-171 Rev 3 CPRT Knowledge Graph...</span>
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="pt-2 flex items-center space-x-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask NIST 800-171 compliance question..."
            className="flex-1 bg-slate-900 border border-slate-800 focus:border-cyan-500 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition flex items-center space-x-1.5"
          >
            <span>Ask</span>
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Right XAI Visualizer Column */}
      <div className="lg:col-span-5 glass-panel p-4 flex flex-col space-y-3 h-full">
        <div className="flex items-center justify-between shrink-0">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center">
            Live Multi-Hop Reasoning Path
          </h3>
          {highlightedControlId && (
            <button
              onClick={() => setHighlightedControlId(null)}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Reset Focus
            </button>
          )}
        </div>

        {/* Compact Graph Window */}
        <div className="h-[310px] shrink-0">
          <GraphVisualizer
            graphData={activeGraph || messages[messages.length - 1]?.graph}
            onNodeSelect={setSelectedNode}
            highlightControlId={highlightedControlId}
          />
        </div>

        {/* Ergonomic Expanded Node Explanation Window */}
        <div className="flex-1 overflow-y-auto min-h-[260px] pr-1">
          {selectedNode ? (
            <div className="p-4 rounded-xl bg-slate-900/90 border border-cyan-500/60 shadow-xl space-y-2.5 text-xs animate-in fade-in slide-in-from-bottom-2">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-cyan-300 font-bold text-sm">{selectedNode.label}</span>
                  <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] uppercase font-mono">
                    {selectedNode.type}
                  </span>
                </div>
                <button onClick={() => setSelectedNode(null)} className="text-slate-400 hover:text-white text-xs px-2 py-0.5 rounded bg-slate-800">
                  ✕ Close
                </button>
              </div>

              {selectedNode.description && (
                <div className="text-slate-200 leading-relaxed pt-1">
                  <strong className="text-cyan-400">Control Description:</strong>
                  <p className="mt-1 text-slate-300 bg-slate-950/60 p-2.5 rounded border border-slate-800/80">{selectedNode.description}</p>
                </div>
              )}

              {selectedNode.detail && (
                <div className="text-slate-300 italic pt-1 bg-slate-950/40 p-2.5 rounded border border-slate-800/60">
                  "{selectedNode.detail}"
                </div>
              )}

              {selectedNode.guidance && (
                <div className="p-3 rounded bg-cyan-950/50 border border-cyan-800/80 text-cyan-200 mt-2 space-y-1">
                  <strong className="text-cyan-400 block font-semibold">Small Business Action:</strong>
                  <p className="text-slate-200 leading-relaxed">{selectedNode.guidance}</p>
                </div>
              )}

              {selectedNode.details && (
                <div className="text-slate-400 font-mono text-[11px] pt-1 bg-slate-950 p-2 rounded border border-slate-800">
                  {selectedNode.details}
                </div>
              )}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-4 rounded-xl bg-slate-950/50 border border-slate-800/80 text-center text-xs text-slate-400">
              <div>
                <div className="text-cyan-400 font-semibold mb-1 text-sm">🔍 Node Details & XAI Trace</div>
                <p className="max-w-xs text-slate-400">Click on any graph node or <span className="text-amber-300 font-mono">[Trace ID]</span> link to view its full description, objectives, and small business guidance here.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
