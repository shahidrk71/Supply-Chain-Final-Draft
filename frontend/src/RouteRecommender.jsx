import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertCircle, AlertTriangle, ArrowRight, ArrowRightLeft, BarChart3,
  CheckCircle2, ChevronDown, Clock3, DollarSign, Download, Gauge, Globe2,
  History, Layers3, MapPin, Menu, Navigation, Package, Plane, RefreshCw,
  Route, Search, Shield, ShieldAlert, ShieldCheck, Ship, Sparkles, Terminal,
  Train, Truck, X, Zap
} from 'lucide-react';

const prettyNumber = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined, { maximumFractionDigits: digits }) : '--';
const money = (value) => Number.isFinite(Number(value)) ? `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '--';

const RouteRecommender = ({ onNavigate }) => {
  const [source, setSource] = useState('');
  const [destination, setDestination] = useState('');
  const [transportMode, setTransportMode] = useState('any');
  const [routingPolicy, setRoutingPolicy] = useState('STRICT');
  const [operationalConfig, setOperationalConfig] = useState('NORMAL');
  const [cargoType, setCargoType] = useState('general');
  const [priority, setPriority] = useState('normal');
  const [budgetSensitivity, setBudgetSensitivity] = useState('medium');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState({ source: '', dest: '' });
  const [searchResults, setSearchResults] = useState({ source: [], dest: [] });
  const [scenarios, setScenarios] = useState([]);
  const [routeHistory, setRouteHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('supplychainer_route_history') || '[]'); } catch { return []; }
  });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [mobilePanel, setMobilePanel] = useState(false);

  useEffect(() => {
    fetch('/api/scenarios')
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`Scenario request failed (${r.status})`)))
      .then(data => setScenarios(Array.isArray(data) ? data : []))
      .catch(() => setScenarios([]));
  }, []);

  const activeScenario = useMemo(() => scenarios.find(s => s.id === operationalConfig), [scenarios, operationalConfig]);

  const getRecommendations = async () => {
    if (!source || !destination) {
      setError('Select both an origin and destination before dispatching the optimizer.');
      return;
    }
    if (source === destination) {
      setError('Origin and destination must be different hubs.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source, destination,
          transport_preference: transportMode,
          routing_policy: routingPolicy,
          cargo_type: cargoType,
          priority,
          budget_sensitivity: budgetSensitivity,
          scenario: operationalConfig !== 'NORMAL' ? operationalConfig : null
        })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || data?.error || `Request failed (${res.status})`);
      if (data.error) throw new Error(data.error);
      const results = Array.isArray(data.recommendations) ? data.recommendations : [];
      setRecommendations(results);
      const entry = {
        timestamp: new Date().toISOString(), source, destination, transportMode, routingPolicy,
        cargoType, priority, budgetSensitivity, scenario: operationalConfig, recommendations: results
      };
      const next = [entry, ...routeHistory].slice(0, 20);
      setRouteHistory(next);
      localStorage.setItem('supplychainer_route_history', JSON.stringify(next));
    } catch (err) {
      setError(err.message || 'Engine connection failed. Verify backend status.');
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  const exportAuditCsv = () => {
    if (!recommendations.length) return;
    const rows = [['Persona','ETA (h)','Cost','Threat','p85 Delay (h)','Scenario Delay (h)','Route']];
    recommendations.forEach(r => {
      const route = (r.legs || []).map(l => l.to_name).join(' -> ');
      rows.push([r.persona, r.adjusted_eta, r.total_cost, r.threat_level, r.audit_trace?.eta?.p85 ?? '', r.audit_trace?.eta?.scenario ?? '', route]);
    });
    const csv = rows.map(row => row.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `supplychainer-audit-${Date.now()}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const clearHistory = () => { setRouteHistory([]); localStorage.removeItem('supplychainer_route_history'); };

  const getModeIcon = (mode = '') => {
    switch (mode.toLowerCase()) {
      case 'air': return <Plane size={13} />;
      case 'sea': return <Ship size={13} />;
      case 'rail': return <Train size={13} />;
      case 'road': return <Truck size={13} />;
      case 'transfer': return <ArrowRightLeft size={13} />;
      default: return <Navigation size={13} />;
    }
  };

  const handleSearch = async (type, query) => {
    setSearchQuery(prev => ({ ...prev, [type]: query }));
    if (type === 'source') setSource(query);
    else setDestination(query);
    if (query.length < 2) { setSearchResults(prev => ({ ...prev, [type]: [] })); return; }
    try {
      const res = await fetch(`/api/hubs/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('search failed');
      const data = await res.json();
      setSearchResults(prev => ({ ...prev, [type]: Array.isArray(data) ? data : [] }));
    } catch { setSearchResults(prev => ({ ...prev, [type]: [] })); }
  };

  const selectHub = (type, hub) => {
    if (type === 'source') { setSource(hub.id); setSearchQuery(prev => ({ ...prev, source: hub.display_name })); }
    else { setDestination(hub.id); setSearchQuery(prev => ({ ...prev, dest: hub.display_name })); }
    setSearchResults(prev => ({ ...prev, [type]: [] }));
  };

  const loadSuezDemo = () => {
    setSource('Mumbai'); setDestination('Rotterdam');
    setSearchQuery({ source: 'Mumbai', dest: 'Rotterdam' });
    setTransportMode('sea'); setRoutingPolicy('STRICT'); setBudgetSensitivity('medium');
    const scenario = scenarios.find(s => /suez/i.test(s.id) || /suez/i.test(s.name || ''));
    setOperationalConfig(scenario?.id || 'SUEZ_BLOCK');
    setMobilePanel(false);
  };

  const primary = recommendations[0];
  const scenarioDelay = recommendations.reduce((sum, r) => sum + Number(r.audit_trace?.eta?.scenario || 0), 0);
  const bypassedScenario = operationalConfig !== 'NORMAL' && recommendations.length > 0 && recommendations.every(r => Number(r.audit_trace?.eta?.scenario || 0) === 0);
  const minCost = recommendations.length ? Math.min(...recommendations.map(r => Number(r.total_cost) || Infinity)) : null;
  const minRisk = recommendations.length ? Math.min(...recommendations.map(r => Number(r.threat_level) || 0)) * 100 : null;

  return (
    <div className="command-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><Globe2 size={21} /></div>
          <div>
            <div className="brand-title">SUPPLYCHAINER <span>COMMAND</span></div>
            <div className="brand-subtitle">Agentic logistics intelligence · multimodal decision engine</div>
          </div>
        </div>
        <div className="topbar-center">
          <span className="live-dot" /> LIVE ENGINE
          <span className="topbar-separator" />
          <span className="mono">p85 QUANTILE</span>
        </div>
        <div className="top-actions">
          <button className="ghost-btn" onClick={() => onNavigate('map')}><MapPin size={15}/> Network</button>
          <button className="ghost-btn" onClick={() => onNavigate('benchmark')}><BarChart3 size={15}/> Benchmarks</button>
          <button className="ghost-btn" onClick={() => onNavigate('suppliers')}><ShieldCheck size={15}/> Suppliers</button>
          <button className="icon-btn mobile-only" onClick={() => setMobilePanel(v => !v)} aria-label="Toggle controls"><Menu size={18}/></button>
        </div>
      </header>

      <div className="command-body">
        <aside className={`control-rail ${mobilePanel ? 'mobile-open' : ''}`}>
          <div className="rail-heading">
            <div><div className="eyebrow">Mission setup</div><h2>Route optimizer</h2></div>
            <button className="icon-btn mobile-only" onClick={() => setMobilePanel(false)}><X size={17}/></button>
          </div>

          <button className="demo-launch" onClick={loadSuezDemo}>
            <div className="demo-icon"><Sparkles size={16}/></div>
            <div><strong>Run Suez stress test</strong><span>Mumbai → Rotterdam · Sea</span></div>
            <ArrowRight size={16}/>
          </button>

          <div className="field-stack">
            <div className="field-label"><MapPin size={12}/> ORIGIN</div>
            <div className="search-field"><Search size={15}/><input value={searchQuery.source} onChange={e => handleSearch('source', e.target.value)} placeholder="Search hub or city" /></div>
            {searchResults.source.length > 0 && <div className="search-menu">{searchResults.source.slice(0, 6).map((h, idx) => <button key={`${h.id}-${idx}`} onClick={() => selectHub('source', h)}>{h.display_name}</button>)}</div>}
          </div>

          <div className="route-divider"><span></span><ArrowRight size={13}/><span></span></div>

          <div className="field-stack">
            <div className="field-label"><Navigation size={12}/> DESTINATION</div>
            <div className="search-field"><Search size={15}/><input value={searchQuery.dest} onChange={e => handleSearch('dest', e.target.value)} placeholder="Search hub or city" /></div>
            {searchResults.dest.length > 0 && <div className="search-menu">{searchResults.dest.slice(0, 6).map((h, idx) => <button key={`${h.id}-${idx}`} onClick={() => selectHub('dest', h)}>{h.display_name}</button>)}</div>}
          </div>

          <div className="field-grid">
            <label><span>Transport</span><select value={transportMode} onChange={e => setTransportMode(e.target.value)}><option value="any">Any mode</option><option value="sea">Sea</option><option value="air">Air</option><option value="rail">Rail</option><option value="road">Road</option></select></label>
            <label><span>Priority</span><select value={priority} onChange={e => setPriority(e.target.value)}><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option></select></label>
          </div>
          <div className="field-grid">
            <label><span>Policy</span><select value={routingPolicy} onChange={e => setRoutingPolicy(e.target.value)}><option value="STRICT">Strict</option><option value="PREFERRED">Preferred</option></select></label>
            <label><span>Budget</span><select value={budgetSensitivity} onChange={e => setBudgetSensitivity(e.target.value)}><option value="low">Cost</option><option value="medium">Balanced</option><option value="high">Time</option></select></label>
          </div>
          <label className="full-field"><span>Cargo profile</span><select value={cargoType} onChange={e => setCargoType(e.target.value)}><option value="general">General cargo</option><option value="electronics">Electronics</option><option value="perishable">Perishable</option><option value="hazardous">Hazardous</option></select></label>
          <label className={`scenario-select ${operationalConfig !== 'NORMAL' ? 'active' : ''}`}><span><AlertTriangle size={12}/> Operational scenario</span><select value={operationalConfig} onChange={e => setOperationalConfig(e.target.value)}><option value="NORMAL">Normal operations</option>{scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>

          <button className="dispatch-primary" onClick={getRecommendations} disabled={loading}>
            {loading ? <><RefreshCw size={17} className="spin"/> Running intelligence...</> : <><Zap size={17}/> Generate strategic routes <ArrowRight size={16}/></>}
          </button>

          <div className="rail-footer">
            <div className="integrity-chip"><ShieldCheck size={14}/><span>Model integrity online</span><i></i></div>
            <div className="rail-tools"><button onClick={exportAuditCsv} disabled={!recommendations.length}><Download size={13}/> Export audit</button><button onClick={() => setHistoryOpen(true)}><History size={13}/> History ({routeHistory.length})</button></div>
          </div>
        </aside>

        <main className="workspace">
          <div className="workspace-head">
            <div>
              <div className="eyebrow">Executive decision surface</div>
              <h1>Network strategy <span>at a glance.</span></h1>
              <p>Compare speed, cost and disruption exposure before dispatch.</p>
            </div>
            {activeScenario && <div className="scenario-pill"><span className="pulse-dot"></span><div><strong>{activeScenario.name}</strong><small>Scenario simulation active</small></div></div>}
          </div>

          {error && <div className="error-banner"><AlertCircle size={18}/><div><strong>Optimizer could not complete</strong><span>{error}</span></div><button onClick={() => setError(null)}><X size={15}/></button></div>}

          {operationalConfig !== 'NORMAL' && <div className={`scenario-alert ${bypassedScenario ? 'safe' : ''}`}><div className="scenario-alert-icon">{bypassedScenario ? <ShieldCheck size={19}/> : <ShieldAlert size={19}/>}</div><div><strong>{bypassedScenario ? 'Disruption bypassed' : 'Global disruption detected'}</strong><span>{bypassedScenario ? `${activeScenario?.name || 'Active scenario'} is avoided across the displayed recommendations.` : `${activeScenario?.name || 'Active scenario'} still affects at least one displayed route.`}</span></div><span className="scenario-value">{bypassedScenario ? '0h impact' : `+${prettyNumber(scenarioDelay)}h`}</span></div>}

          <div className="kpi-row">
            <div className="kpi-card"><div className="kpi-icon blue"><Route size={17}/></div><div><span>OPTIONS</span><strong>{recommendations.length || '—'}</strong><small>decision paths</small></div></div>
            <div className="kpi-card"><div className="kpi-icon amber"><Clock3 size={17}/></div><div><span>FASTEST</span><strong>{primary ? `${prettyNumber(primary.adjusted_eta)}h` : '—'}</strong><small>adjusted ETA</small></div></div>
            <div className="kpi-card"><div className="kpi-icon green"><DollarSign size={17}/></div><div><span>LOWEST COST</span><strong>{minCost !== null ? money(minCost) : '—'}</strong><small>landed estimate</small></div></div>
            <div className="kpi-card"><div className="kpi-icon violet"><Shield size={17}/></div><div><span>RISK FLOOR</span><strong>{minRisk !== null ? `${prettyNumber(minRisk)}%` : '—'}</strong><small>threat exposure</small></div></div>
          </div>

          {recommendations.length === 0 && !loading ? (
            <div className="empty-state">
              <div className="empty-orbit"><div><Route size={31}/></div><span></span><span></span><span></span></div>
              <div className="empty-copy"><div className="eyebrow">Awaiting dispatch brief</div><h2>Build a route strategy</h2><p>Choose an origin and destination, then let the engine evaluate live intelligence, scenario exposure and the p85 delay model.</p><div className="empty-actions"><button onClick={loadSuezDemo}><Sparkles size={15}/> Try the Suez stress test</button><button className="secondary" onClick={() => onNavigate('map')}><MapPin size={15}/> Explore the network</button></div></div>
            </div>
          ) : (
            <div className="results-wrap">
              <div className="results-heading"><div><span className="eyebrow">Decision set</span><h2>Recommended pathways</h2></div><span className="result-meta"><Activity size={13}/> {recommendations.length} evaluated options</span></div>
              <div className="route-grid">
                {recommendations.map((rec, idx) => {
                  const threat = Math.max(0, Math.min(100, Number(rec.threat_level || 0) * 100));
                  const p85 = Number(rec.audit_trace?.eta?.p85 || 0);
                  const scenario = Number(rec.audit_trace?.eta?.scenario || 0);
                  const personaClass = rec.persona === 'FASTEST' ? 'fastest' : rec.persona === 'SAFEST' ? 'safest' : 'balanced';
                  return <article className={`route-card ${idx === 0 ? 'featured' : ''}`} key={`${rec.persona}-${idx}`}>
                    <div className="route-card-top"><div className={`persona-tag ${personaClass}`}>{rec.persona === 'BALANCED' && <Gauge size={12}/>} {rec.persona === 'FASTEST' && <Zap size={12}/>} {rec.persona === 'SAFEST' && <ShieldCheck size={12}/>} {rec.persona}</div><span className="route-rank">OPTION {idx + 1}</span></div>
                    <div className="route-hero"><div><span>ADJUSTED ETA</span><strong>{prettyNumber(rec.adjusted_eta)}<em>h</em></strong></div><div className="route-cost"><span>LANDED COST</span><strong>{money(rec.total_cost)}</strong></div></div>
                    <div className="route-explanation">{rec.explanation}</div>
                    <div className="route-timeline">
                      {(rec.legs || []).map((leg, lIdx) => <React.Fragment key={lIdx}>
                        <div className={`timeline-node ${leg.type === 'transfer' ? 'transfer' : ''}`}><div className="node-dot">{getModeIcon(leg.mode)}</div><div><span>{leg.type === 'transfer' ? 'HANDOFF' : (leg.mode || 'TRANSIT').toUpperCase()}</span><strong>{leg.to_name}</strong></div></div>
                        {lIdx < rec.legs.length - 1 && <div className="timeline-line"/>}
                      </React.Fragment>)}
                    </div>
                    <div className="route-metrics"><div><Clock3 size={13}/><span>p85 buffer</span><strong>+{prettyNumber(p85)}h</strong></div><div><ShieldAlert size={13}/><span>threat</span><strong>{prettyNumber(threat)}%</strong></div><div><AlertTriangle size={13}/><span>scenario</span><strong className={scenario > 0 ? 'danger' : 'safe-text'}>{scenario > 0 ? `+${prettyNumber(scenario)}h` : 'clear'}</strong></div></div>
                    <div className="route-card-foot"><span><CheckCircle2 size={13}/> Decision-ready</span><button onClick={() => setHistoryOpen(true)}>View audit <ArrowRight size={13}/></button></div>
                  </article>;
                })}
              </div>
            </div>
          )}
        </main>

        <aside className="intel-rail">
          <div className="intel-heading"><div><div className="eyebrow">Explainability</div><h2>Decision audit</h2></div><span className="secure-icon"><ShieldCheck size={16}/></span></div>
          {primary ? <>
            <div className="audit-hero"><div className="audit-status"><span className="live-dot"></span> MODEL TRACE VERIFIED</div><strong>{primary.persona}</strong><span>Selected reference pathway</span></div>
            <div className="audit-section"><div className="audit-title"><Clock3 size={13}/> ETA decomposition</div><div className="audit-row"><span>Base transit</span><strong>{prettyNumber(primary.audit_trace?.eta?.transit)}h</strong></div><div className="audit-row"><span>Transfer handling</span><strong>+{prettyNumber(primary.audit_trace?.eta?.transfer)}h</strong></div><div className="audit-row"><span>p85 risk buffer</span><strong>+{prettyNumber(primary.audit_trace?.eta?.p85)}h</strong></div><div className="audit-row"><span>Scenario impact</span><strong className={Number(primary.audit_trace?.eta?.scenario || 0) > 0 ? 'danger' : 'safe-text'}>{Number(primary.audit_trace?.eta?.scenario || 0) > 0 ? `+${prettyNumber(primary.audit_trace.eta.scenario)}h` : 'None'}</strong></div></div>
            <div className="audit-section"><div className="audit-title"><DollarSign size={13}/> Cost composition</div><div className="audit-row"><span>Transit</span><strong>{money(primary.audit_trace?.cost?.transit)}</strong></div><div className="audit-row"><span>Transfer fees</span><strong>{money(primary.audit_trace?.cost?.transfer)}</strong></div><div className="audit-row"><span>Scenario premium</span><strong>{money(primary.audit_trace?.cost?.scenario)}</strong></div></div>
            <div className="model-note"><Sparkles size={14}/><div><strong>Why this route?</strong><span>Network topology, live signals, scenario state and the p85 quantile model were evaluated together.</span></div></div>
          </> : <div className="intel-empty"><Layers3 size={34}/><p>Run a strategy to reveal the model's evidence trail.</p></div>}
          <div className="truth-footer"><ShieldCheck size={14}/><span>CANONICAL NETWORK · AUDITABLE</span></div>
        </aside>
      </div>

      <footer className="statusbar"><div><span className="status-dot"></span> ENGINE ONLINE</div><span>LIVE NEWS</span><span>CARF FILTER</span><span>NLP THREAT</span><span>P85 QUANTILE</span><span className="status-spacer"></span><span className="mono">MISSION CONTROL STATUS: STELLAR</span></footer>

      {historyOpen && <div className="modal-backdrop" onClick={() => setHistoryOpen(false)}><div className="history-modal" onClick={e => e.stopPropagation()}><div className="modal-head"><div><div className="eyebrow">Local decision archive</div><h2>Route history</h2></div><button className="icon-btn" onClick={() => setHistoryOpen(false)}><X size={18}/></button></div>{routeHistory.length ? <div className="history-list">{routeHistory.map((h, i) => <button key={`${h.timestamp}-${i}`} className="history-item" onClick={() => { setSource(h.source); setDestination(h.destination); setSearchQuery({source: h.source, dest: h.destination}); setTransportMode(h.transportMode); setRoutingPolicy(h.routingPolicy); setBudgetSensitivity(h.budgetSensitivity); setOperationalConfig(h.scenario || 'NORMAL'); setRecommendations(h.recommendations || []); setHistoryOpen(false); }}><div><strong>{h.source} <ArrowRight size={12}/> {h.destination}</strong><span>{new Date(h.timestamp).toLocaleString()}</span></div><span>{h.recommendations?.length || 0} options</span></button>)}</div> : <div className="history-empty"><History size={30}/><p>No saved route runs yet.</p></div>}<div className="modal-foot"><button className="danger-btn" onClick={clearHistory} disabled={!routeHistory.length}>Clear archive</button><span>Stored locally on this device · max 20 runs</span></div></div></div>}
    </div>
  );
};

export default RouteRecommender;
