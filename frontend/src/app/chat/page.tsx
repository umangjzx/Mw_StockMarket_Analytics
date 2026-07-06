"use client";

import { useState, useRef, useEffect } from "react";
import { Plus, Send, Loader2, ExternalLink, Brain, Sparkles, MessageSquareQuote, Database, Menu } from "lucide-react";
import { chatApi } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { EmptyState } from "@/components/ui/ErrorState";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: any[];
  retrieved?: number;
  model?: string;
}

interface Session { id: string; ticker?: string; created_at: string; }

export default function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [ticker, setTicker] = useState("");
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function createSession() {
    try {
      const sess: any = await chatApi.createSession({ ticker: ticker || undefined });
      const session: Session = { id: sess.id, ticker: sess.ticker, created_at: sess.created_at };
      setSessions((s) => [session, ...s]);
      setActiveSession(session);
      setMessages([]);
      setShowMobileSidebar(false);
    } catch (e: any) {
      alert(`Failed to create session: ${e.message}`);
    }
  }

  async function sendMessage() {
    if (!input.trim() || !activeSession || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res: any = await chatApi.sendMessage(activeSession.id, { question, top_k: 10 });
      setMessages((m) => [...m, {
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        retrieved: res.retrieved_chunks,
        model: res.model_used,
      }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full relative overflow-hidden" style={{ height: "calc(100vh - 57px)" }}>
      {/* Mobile Overlay */}
      {showMobileSidebar && (
        <div className="md:hidden absolute inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={() => setShowMobileSidebar(false)} />
      )}

      {/* Session Sidebar */}
      <div className={`absolute inset-y-0 left-0 z-50 w-64 flex-shrink-0 border-r border-white/5 flex flex-col transform transition-transform duration-300 md:relative md:translate-x-0 ${showMobileSidebar ? "translate-x-0" : "-translate-x-full"}`} style={{ background: "var(--bg-surface)" }}>
        <div className="p-4 border-b border-white/5">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Sessions</p>
          <div className="flex flex-col gap-2 mb-3">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Context Ticker (Optional)"
              className="input-field text-xs font-mono w-full"
              id="chat-ticker-input"
            />
          </div>
          <button onClick={createSession} className="btn-primary w-full text-xs justify-center shadow-md shadow-blue-900/20" id="new-session-btn">
            <Plus size={14} /> New Chat Session
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sessions.length === 0 && (
            <p className="text-[11px] text-slate-600 p-2 text-center mt-4">No recent sessions</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => { setActiveSession(s); setMessages([]); setShowMobileSidebar(false); }}
              className={`w-full text-left p-3 rounded-xl transition-all group border ${
                activeSession?.id === s.id
                  ? "bg-blue-500/10 border-blue-500/30 shadow-inner"
                  : "bg-transparent border-transparent hover:bg-white/[0.03] hover:border-white/5"
              }`}
            >
              <p className={`font-bold text-sm truncate transition-colors ${activeSession?.id === s.id ? 'text-blue-400' : 'text-slate-300 group-hover:text-white'}`}>
                {s.ticker ? (
                  <span className="flex items-center gap-1.5"><MessageSquareQuote size={12} className="text-slate-500" /> {s.ticker}</span>
                ) : (
                  <span className="flex items-center gap-1.5"><Brain size={12} className="text-slate-500" /> General</span>
                )}
              </p>
              <p className="text-[10px] text-slate-600 mt-1 pl-4 font-medium">{fmtDate(s.created_at)}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 bg-black/40 relative">
        {/* Mobile Header Toggle */}
        <div className="md:hidden p-3 border-b border-white/5 flex items-center bg-black/60">
          <button onClick={() => setShowMobileSidebar(true)} className="btn-ghost p-1.5 rounded-md text-slate-400 hover:text-white">
            <Menu size={20} />
          </button>
          <span className="ml-3 font-bold text-sm tracking-tight text-white">AI Chat</span>
        </div>

        {!activeSession ? (
          <div className="flex-1 flex items-center justify-center p-6 fade-in">
            <div className="text-center space-y-5 max-w-md">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/30 flex items-center justify-center mx-auto shadow-[0_0_40px_rgba(59,130,246,0.15)] relative">
                <Brain size={32} className="text-blue-400 relative z-10" />
                <Sparkles size={16} className="text-purple-400 absolute top-3 right-3 animate-pulse" />
              </div>
              <div>
                <h2 className="text-2xl font-black text-white mb-2 tracking-tight">AI Market <span className="gradient-text">Intelligence</span></h2>
                <p className="text-sm text-slate-400 leading-relaxed max-w-sm mx-auto">
                  Ask nuanced questions about stock trends, analyst commentary, or market sentiment.
                  Answers are strictly grounded in analyzed YouTube video transcripts.
                </p>
              </div>
              <button onClick={createSession} className="btn-primary mx-auto px-6 py-2.5 text-sm shadow-lg shadow-blue-900/20" id="start-chat-btn">
                <Plus size={15} className="mr-1" /> Start Your First Session
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-6">
              {messages.length === 0 && (
                <div className="flex items-center justify-center h-full fade-in">
                  <div className="text-center">
                    <Brain size={32} className="text-slate-700 mx-auto mb-4" />
                    <h3 className="text-lg font-bold text-slate-400">
                      {activeSession.ticker ? `Chatting about ${activeSession.ticker}` : "General Market Chat"}
                    </h3>
                    <p className="text-sm text-slate-600 mt-1">Every answer cites exact video timestamps.</p>
                  </div>
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`flex fade-in ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-5 ${
                    m.role === "user" 
                      ? "bg-blue-600 text-white shadow-md shadow-blue-900/20 rounded-tr-sm" 
                      : "glass-card card-accent-blue bg-black/60 shadow-lg rounded-tl-sm"
                  }`}>
                    <p className={`text-[15px] leading-relaxed whitespace-pre-wrap ${m.role === "user" ? "text-white" : "text-slate-200"}`}>
                      {m.content}
                    </p>

                    {m.citations && m.citations.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-white/10 space-y-2">
                        <p className="text-[10px] text-blue-400 font-bold uppercase tracking-widest flex items-center gap-1.5">
                          <Database size={11} />
                          Synthesized from {m.retrieved} sources
                        </p>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {m.citations.map((c: any, ci: number) => (
                            <a
                              key={ci}
                              href={`https://youtube.com/watch?v=${c.video_id}&t=${Math.floor(c.start_seconds ?? 0)}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 text-[11px] text-slate-300 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/30 pl-1.5 pr-2.5 py-1 rounded-md transition-all group"
                            >
                              <span className="font-mono text-blue-400 font-bold bg-blue-500/10 px-1.5 rounded text-[10px]">[{ci + 1}]</span>
                              <span className="max-w-[200px] truncate">{c.video_title}</span>
                              <ExternalLink size={10} className="opacity-40 group-hover:opacity-100 text-blue-400 transition-opacity" />
                            </a>
                          ))}
                        </div>
                        {m.model && <p className="text-[9px] text-slate-600 mt-3 font-mono">Generative Engine: {m.model}</p>}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start fade-in">
                  <div className="glass-card card-accent-purple bg-black/60 rounded-2xl rounded-tl-sm p-5 w-24 flex justify-center shadow-lg">
                    <div className="flex gap-1.5 items-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="p-4 md:p-6 bg-gradient-to-t from-black via-black/80 to-transparent">
              <div className="max-w-4xl mx-auto relative group">
                {/* Glow behind input */}
                <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/30 to-purple-500/30 rounded-xl blur opacity-30 group-focus-within:opacity-100 transition duration-500" />
                <div className="relative flex gap-3 bg-black border border-white/10 rounded-xl p-2 shadow-2xl">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                    placeholder={activeSession.ticker ? `Ask about ${activeSession.ticker} (Enter to send)` : "Ask about stocks, earnings, market trends… (Enter to send)"}
                    className="w-full bg-transparent border-none outline-none text-[14px] text-white placeholder-slate-500 resize-none p-3 focus:ring-0"
                    id="chat-message-input"
                    rows={1}
                    style={{ minHeight: "44px", maxHeight: "160px" }}
                    disabled={loading}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={loading || !input.trim()}
                    className="w-12 h-12 flex-shrink-0 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded-lg flex items-center justify-center transition-all disabled:opacity-50 self-end shadow-md"
                    id="chat-send-btn"
                  >
                    {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} className="-ml-0.5" />}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
