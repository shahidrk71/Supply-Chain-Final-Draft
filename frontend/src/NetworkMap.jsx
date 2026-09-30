import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { ArrowLeft, Map as MapIcon, RefreshCw } from 'lucide-react';

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(points.map(p => [p.lat, p.lon]), { padding: [30, 30], maxZoom: 4 });
    }
  }, [map, points]);
  return null;
}

export default function NetworkMap({ onBack }) {
  const [network, setNetwork] = useState({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const r = await fetch('/api/network');
      if (!r.ok) throw new Error(`Network request failed (${r.status})`);
      setNetwork(await r.json());
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const points = useMemo(() => network.nodes.filter(n => Number.isFinite(n.lat) && Number.isFinite(n.lon)), [network.nodes]);
  const edgeLines = useMemo(() => {
    const byId = new Map(points.map(n => [n.id, n]));
    return network.edges.slice(0, 1200).map(e => {
      const a = byId.get(e.source), b = byId.get(e.target);
      return a && b ? [[a.lat, a.lon], [b.lat, b.lon]] : null;
    }).filter(Boolean);
  }, [network.edges, points]);

  return (
    <div className="dashboard-layout" style={{ gridTemplateColumns: '1fr' }}>
      <header className="dashboard-header">
        <div style={{display:'flex',alignItems:'center',gap:'1rem'}}>
          <MapIcon size={28} color="#3b82f6" />
          <div><h1 style={{fontSize:'1.25rem',fontWeight:800}}>Global Network Map</h1><p style={{fontSize:'0.7rem',color:'#64748b',fontWeight:700}}>LIVE CANONICAL MULTIMODAL TOPOLOGY</p></div>
        </div>
        <div style={{display:'flex',gap:'0.75rem'}}>
          <button className="dispatch-btn" onClick={load}><RefreshCw size={14}/> Refresh</button>
          <button className="dispatch-btn" onClick={onBack}><ArrowLeft size={14}/> Command Console</button>
        </div>
      </header>
      <main className="panel" style={{padding:0,overflow:'hidden',position:'relative'}}>
        {loading && <div style={{padding:'1rem'}}>Loading canonical network…</div>}
        {error && <div style={{padding:'1rem',color:'#ef4444'}}>{error}</div>}
        {!loading && !error && (
          <MapContainer center={[20, 0]} zoom={2} minZoom={2} style={{height:'72vh',width:'100%'}}>
            <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitBounds points={points} />
            {edgeLines.map((line,i)=><Polyline key={i} positions={line} pathOptions={{weight:1,opacity:0.16}} />)}
            {points.map(n => (
              <CircleMarker key={n.id} center={[n.lat,n.lon]} radius={n.importance ? Math.max(3, Math.min(8, n.importance/2)) : 4}>
                <Popup><strong>{n.display_name}</strong><br/>{n.mode?.toUpperCase() || 'MULTIMODAL'}<br/>{n.country || ''}</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        )}
        {!loading && !error && <div style={{position:'absolute',left:16,bottom:16,zIndex:1000,background:'rgba(15,23,42,.92)',padding:'10px 14px',borderRadius:8,fontSize:12}}>{points.length} mapped virtual nodes · {network.edges.length} directed edges</div>}
      </main>
    </div>
  );
}
