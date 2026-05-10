import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  Cpu, LayoutDashboard, Activity, DollarSign, Settings,
  Send, AlertTriangle, CheckCircle, Zap, ArrowUpCircle,
  Clock, Hash, TrendingDown, Shield, ChevronRight, 
  Circle, Layers, GitBranch, BarChart2
} from 'lucide-react'
import './App.css'

// ─── constants ───────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

const TIER_META = {
  1: { label: 'Tier 1 · Lightweight', color: '#10b981', bg: 'rgba(16,185,129,0.12)', model: 'llama3.2:1b / ollama' },
  2: { label: 'Tier 2 · Mid-Range',   color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', model: 'gpt-4o-mini / openai' },
  3: { label: 'Tier 3 · Frontier',    color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)', model: 'gpt-4o / openai' },
}

const SAMPLE_PROMPTS = [
  { text: 'What is 2 + 2?',                              hint: 'low',    mode: 'none',  tag: 'Tier 1 Demo' },
  { text: 'Explain the difference between REST and GraphQL APIs.', hint: 'medium', mode: 'async', tag: 'Tier 2 Demo' },
  { text: 'Design a production-grade distributed rate limiter with Redis and sliding window algorithm. Include architecture, code, and failure modes.', hint: 'high', mode: 'sync', tag: 'Tier 3 + Escalation' },
]

// ─── components ──────────────────────────────────────────────────────────────

function StatusDot({ ok }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: ok ? '#10b981' : '#ef4444',
      boxShadow: ok ? '0 0 8px #10b981' : '0 0 8px #ef4444',
    }} />
  )
}

function TierBadge({ tier }) {
  const m = TIER_META[tier] || TIER_META[1]
  return (
    <span style={{
      padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700,
      color: m.color, background: m.bg, letterSpacing: 0.5,
    }}>{m.label}</span>
  )
}

function TraceCard({ item, index }) {
  const [expanded, setExpanded] = useState(index === 0)
  const m = TIER_META[item.tier] || TIER_META[1]

  return (
    <div className="trace-card" style={{ borderColor: m.color + '40' }}>
      <div className="trace-card-header" onClick={() => setExpanded(e => !e)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <TierBadge tier={item.tier} />
          {item.escalated && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#f59e0b', fontSize: 11, fontWeight: 600 }}>
              <ArrowUpCircle size={13} /> ESCALATED
            </span>
          )}
          {item.verified === true  && <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#10b981', fontSize: 11 }}><CheckCircle size={13} /> Verified</span>}
          {item.verified === false && <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#ef4444', fontSize: 11 }}><AlertTriangle size={13} /> Failed</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: '#64748b' }}>
          <span><Clock size={12} style={{ marginRight: 4 }} />{item.latency_ms.toFixed(0)}ms</span>
          <ChevronRight size={14} style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: '0.2s' }} />
        </div>
      </div>

      {expanded && (
        <div className="trace-card-body">
          <div className="trace-grid">
            <MetricRow icon={<Layers size={13} />}    label="Model"    value={item.model_used} />
            <MetricRow icon={<GitBranch size={13} />} label="Provider" value={item.provider} />
            <MetricRow icon={<Hash size={13} />}      label="Tokens"   value={`${item.prompt_tokens} in / ${item.completion_tokens} out`} />
            <MetricRow icon={<DollarSign size={13} />} label="Cost"    value={`$${item.cost_usd.toFixed(5)}`} />
            <MetricRow icon={<TrendingDown size={13} />} label="Saved" value={`$${item.savings_usd.toFixed(5)} (${item.savings_pct.toFixed(1)}%)`} highlight />
            <MetricRow icon={<Shield size={13} />}    label="Verified" value={item.verified === null ? 'Async / Pending' : item.verified ? 'Pass' : 'Fail → Escalated'} />
          </div>

          <div className="trace-output">
            <span className="trace-output-label">Response</span>
            <pre>{item.output}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

function MetricRow({ icon, label, value, highlight }) {
  return (
    <div className="metric-row">
      <span className="metric-label">{icon}{label}</span>
      <span className="metric-value" style={{ color: highlight ? '#10b981' : undefined }}>{value}</span>
    </div>
  )
}

function CostPanel({ requests }) {
  const totalActual   = requests.reduce((a, r) => a + r.cost_usd, 0)
  const totalSavings  = requests.reduce((a, r) => a + r.savings_usd, 0)
  const totalBaseline = totalActual + totalSavings
  const pct = totalBaseline > 0 ? (totalSavings / totalBaseline) * 100 : 0

  const tier1 = requests.filter(r => r.tier === 1).length
  const tier2 = requests.filter(r => r.tier === 2).length
  const tier3 = requests.filter(r => r.tier === 3).length
  const escalated = requests.filter(r => r.escalated).length

  return (
    <div className="cost-panel">
      <div className="panel-header">
        <h3><BarChart2 size={16} className="icon-accent" /> Cost Analytics</h3>
      </div>
      <div className="cost-body">
        <div className="cost-stat-row">
          <CostStat label="Actual Spend" value={`$${totalActual.toFixed(5)}`} />
          <CostStat label="Baseline Cost" value={`$${totalBaseline.toFixed(5)}`} muted />
          <CostStat label="Net Saved" value={`$${totalSavings.toFixed(5)}`} green />
        </div>

        <div className="savings-bar-container">
          <div className="savings-bar-label">
            <span>Savings Rate</span>
            <span style={{ color: '#10b981', fontWeight: 700 }}>{pct.toFixed(1)}%</span>
          </div>
          <div className="savings-bar-track">
            <div className="savings-bar-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="routing-dist">
          <span className="routing-dist-label">Routing Distribution</span>
          <div className="routing-dist-bars">
            <TierBar label="T1" count={tier1} total={requests.length} color="#10b981" />
            <TierBar label="T2" count={tier2} total={requests.length} color="#f59e0b" />
            <TierBar label="T3" count={tier3} total={requests.length} color="#8b5cf6" />
          </div>
        </div>

        <div className="stats-grid">
          <SmallStat label="Requests" value={requests.length} icon={<Activity size={14} />} />
          <SmallStat label="Escalations" value={escalated} icon={<ArrowUpCircle size={14} />} warn={escalated > 0} />
          <SmallStat label="Avg Latency" value={requests.length ? (requests.reduce((a,r)=>a+r.latency_ms,0)/requests.length).toFixed(0)+'ms' : '—'} icon={<Zap size={14} />} />
        </div>
      </div>
    </div>
  )
}

function CostStat({ label, value, green, muted }) {
  return (
    <div className="cost-stat">
      <span className="cost-stat-label">{label}</span>
      <span className="cost-stat-value" style={{ color: green ? '#10b981' : muted ? '#475569' : '#f1f5f9' }}>{value}</span>
    </div>
  )
}

function TierBar({ label, count, total, color }) {
  const pct = total > 0 ? (count / total) * 100 : 0
  return (
    <div className="tier-bar-item">
      <span style={{ color, fontWeight: 700, fontSize: 11 }}>{label}</span>
      <div className="tier-bar-track">
        <div className="tier-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, color: '#64748b', width: 16, textAlign: 'right' }}>{count}</span>
    </div>
  )
}

function SmallStat({ label, value, icon, warn }) {
  return (
    <div className="small-stat">
      <span className="small-stat-icon" style={{ color: warn ? '#f59e0b' : '#6366f1' }}>{icon}</span>
      <span className="small-stat-value" style={{ color: warn ? '#f59e0b' : undefined }}>{value}</span>
      <span className="small-stat-label">{label}</span>
    </div>
  )
}

// ─── main app ────────────────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab] = useState('console')
  const [prompt, setPrompt] = useState('')
  const [qualityHint, setQualityHint] = useState('medium')
  const [verifyMode, setVerifyMode] = useState('async')
  const [requests, setRequests] = useState([])
  const [messages, setMessages] = useState([
    { role: 'system', text: 'NeuroRoute is online. Submit a prompt to trigger the intelligent routing pipeline.' }
  ])
  const [loading, setLoading] = useState(false)
  const [apiOk, setApiOk] = useState(false)
  const chatEndRef = useRef(null)

  // Health-check the API on load
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(r => r.ok ? setApiOk(true) : setApiOk(false))
      .catch(() => setApiOk(false))
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = useCallback(async (overridePrompt, overrideHint, overrideMode) => {
    const text = (overridePrompt ?? prompt).trim()
    if (!text || loading) return

    const hint = overrideHint ?? qualityHint
    const mode = overrideMode ?? verifyMode

    setPrompt('')
    setMessages(m => [...m, { role: 'user', text }])
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/v1/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, quality_hint: hint, verification_mode: mode })
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setRequests(r => [data, ...r])
      setMessages(m => [...m, { role: 'ai', text: data.output, meta: data }])
    } catch (e) {
      setMessages(m => [...m, { role: 'error', text: `Router error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }, [prompt, qualityHint, verifyMode, loading])

  const runSample = (s) => {
    setQualityHint(s.hint)
    setVerifyMode(s.mode)
    send(s.text, s.hint, s.mode)
  }

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Cpu size={20} /></div>
          <div>
            <div className="brand-name">NeuroRoute</div>
            <div className="brand-sub">AI Engineering Router</div>
          </div>
        </div>

        <nav className="nav">
          {[
            { id: 'console',   icon: <LayoutDashboard size={17} />, label: 'Console' },
            { id: 'analytics', icon: <BarChart2 size={17} />,       label: 'Analytics' },
          ].map(n => (
            <button key={n.id} className={`nav-btn ${tab === n.id ? 'active' : ''}`} onClick={() => setTab(n.id)}>
              {n.icon} {n.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-section">
          <div className="sidebar-section-title">Quick Demos</div>
          {SAMPLE_PROMPTS.map((s, i) => (
            <button key={i} className="sample-btn" onClick={() => runSample(s)} disabled={loading}>
              <span className="sample-tag">{s.tag}</span>
              <span className="sample-text">{s.text.slice(0, 48)}…</span>
            </button>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="health-row">
            <StatusDot ok={apiOk} />
            <span>{apiOk ? 'API Online' : 'API Offline'}</span>
          </div>
          <div className="health-row" style={{ color: '#475569', fontSize: 11 }}>
            v1.0.0 · FastAPI + React
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <header className="topbar">
          <div>
            <h1 className="page-title">Intelligent LLM Gateway</h1>
            <p className="page-sub">Multi-tier routing · LLM-as-a-judge verification · Auto-escalation · Cost analytics</p>
          </div>
          <div className="topbar-stats">
            <div className="ts-item"><span className="ts-v">{requests.length}</span><span className="ts-l">Requests</span></div>
            <div className="ts-sep" />
            <div className="ts-item"><span className="ts-v">{requests.filter(r=>r.escalated).length}</span><span className="ts-l">Escalations</span></div>
            <div className="ts-sep" />
            <div className="ts-item"><span className="ts-v" style={{color:'#10b981'}}>${requests.reduce((a,r)=>a+r.savings_usd,0).toFixed(4)}</span><span className="ts-l">Saved</span></div>
          </div>
        </header>

        {tab === 'console' && (
          <div className="console-layout">
            {/* Chat */}
            <div className="chat-panel">
              <div className="chat-history">
                {messages.map((m, i) => (
                  <div key={i} className={`msg msg-${m.role}`}>
                    {m.role === 'ai' && m.meta && (
                      <div className="msg-meta">
                        <TierBadge tier={m.meta.tier} />
                        {m.meta.escalated && <span style={{color:'#f59e0b',fontSize:11,display:'flex',alignItems:'center',gap:4}}><ArrowUpCircle size={12}/>Escalated</span>}
                        <span style={{color:'#475569',fontSize:11}}>{m.meta.latency_ms.toFixed(0)}ms</span>
                      </div>
                    )}
                    {m.role === 'system' && <Circle size={14} style={{flexShrink:0,color:'#475569'}} />}
                    {m.role === 'error'  && <AlertTriangle size={14} style={{flexShrink:0,color:'#ef4444'}} />}
                    <pre className="msg-text">{m.text}</pre>
                  </div>
                ))}
                {loading && (
                  <div className="msg msg-ai">
                    <div className="typing-dots"><span/><span/><span/></div>
                    <span style={{color:'#475569',fontSize:13}}>Router processing…</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="input-bar">
                <div className="input-controls">
                  <select value={qualityHint} onChange={e=>setQualityHint(e.target.value)} className="select-sm">
                    <option value="low">Quality: Low (Tier 1)</option>
                    <option value="medium">Quality: Auto-detect</option>
                    <option value="high">Quality: High (Tier 3)</option>
                  </select>
                  <select value={verifyMode} onChange={e=>setVerifyMode(e.target.value)} className="select-sm">
                    <option value="none">Verify: None</option>
                    <option value="async">Verify: Async</option>
                    <option value="sync">Verify: Sync + Escalate</option>
                  </select>
                </div>
                <div className="input-row">
                  <textarea
                    value={prompt}
                    onChange={e=>setPrompt(e.target.value)}
                    onKeyDown={e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()} }}
                    placeholder="Enter a prompt… (Shift+Enter for newline)"
                    rows={3}
                    className="prompt-input"
                    disabled={loading}
                  />
                  <button className="send-btn" onClick={()=>send()} disabled={loading||!prompt.trim()}>
                    <Send size={18} />
                  </button>
                </div>
              </div>
            </div>

            {/* Trace sidebar */}
            <div className="trace-sidebar">
              <div className="panel-header">
                <h3><Activity size={16} className="icon-accent" /> Execution Trace</h3>
                {requests.length > 0 && (
                  <button className="clear-btn" onClick={()=>{setRequests([]);setMessages([{role:'system',text:'Cleared. Ready for new session.'}])}}>
                    Clear
                  </button>
                )}
              </div>
              <div className="trace-list">
                {requests.length === 0
                  ? <div className="empty-state"><Activity size={32} opacity={0.2} /><p>No requests yet</p><p style={{fontSize:12,color:'#334155'}}>Use the Quick Demos or type a prompt</p></div>
                  : requests.map((r, i) => <TraceCard key={r.request_id} item={r} index={i} />)
                }
              </div>
            </div>
          </div>
        )}

        {tab === 'analytics' && (
          <div className="analytics-layout">
            <CostPanel requests={requests} />
            {requests.length === 0 && (
              <div className="empty-state" style={{gridColumn:'1/-1'}}>
                <BarChart2 size={40} opacity={0.2} />
                <p style={{marginTop:12}}>Run some prompts to see analytics</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
