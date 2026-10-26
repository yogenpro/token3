import { useEffect, useState } from 'react';
import { Activity, Archive, ArrowUpRight, ChartNoAxesCombined, CircleHelp, Grid2X2, Building2, Layers, Search, ShieldCheck } from 'lucide-react';
import type { Model } from '../lib/data';
import { Brand, ModelMark } from './UI';
export type View = 'compare' | 'models' | 'providers' | 'changes' | 'historical' | 'coverage' | 'methodology';
const navigation = [
  { id: 'compare', label: 'Compare prices', icon: ChartNoAxesCombined },
  { id: 'models', label: 'Model explorer', icon: Grid2X2 },
  { id: 'providers', label: 'Providers', icon: Building2 },
  { id: 'changes', label: 'Recent changes', icon: Activity },
  { id: 'historical', label: 'Historical evidence', icon: Archive },
  { id: 'coverage', label: 'Coverage', icon: Layers },
  { id: 'methodology', label: 'Methodology', icon: CircleHelp },
] as const;
const storageKey = 'tokentokentoken-recent-models';
function savedRecent(): string[] {
  try { const value: unknown = JSON.parse(localStorage.getItem(storageKey) ?? '[]'); return Array.isArray(value) ? value.filter((id) => typeof id === 'string').slice(0, 6) : []; }
  catch { return []; }
}

export function Sidebar({ models, selected, view, onView, onModel, changeCount }: { models: Model[]; selected: string; view: View; onView: (view: View) => void; onModel: (id: string) => void; changeCount: number }) {
  const [recent, setRecent] = useState(savedRecent);
  const [search, setSearch] = useState('');
  useEffect(() => {
    if (!models.some((m) => m.id === selected)) return;
    setRecent((old) => { const next = [selected, ...old.filter((id) => id !== selected && models.some((m) => m.id === id))].slice(0, 6);
      try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Optional preferences only. */ }
      return next;
    });
  }, [selected, models]);
  const matched = search.trim() ? models.filter((m) => `${m.name} ${m.creator} ${m.family} ${m.id}`.toLowerCase().includes(search.trim().toLowerCase())) : recent.map((id) => models.find((m) => m.id === id)).filter((m): m is Model => !!m);
  return <aside className="sidebar">
    <Brand />
    <nav className="main-nav" aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) =>
      <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => onView(id)} aria-label={label} aria-description={id === 'changes' && changeCount > 0 ? `${changeCount} verified price changes recorded` : undefined} aria-current={view === id ? 'page' : undefined}>
        <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{id === 'changes' && changeCount > 0 && <span className="nav-count">{changeCount}</span>}
      </button>)}
    </nav>
    <div className="watchlist"><label className="search-field sidebar-search"><Search size={14} /><input aria-label="Search reviewed models" placeholder="Find a model…" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <div className="sidebar-label">{search.trim() ? 'MATCHING MODELS' : 'RECENT MODELS'} <span>{matched.length}</span></div>{matched.slice(0, 8).map((model) =>
        <button key={model.id} className={`watch-item ${selected === model.id && view === 'compare' ? 'selected' : ''}`} onClick={() => { onModel(model.id); setSearch(''); }}>
          <ModelMark model={model} small /><span>{model.name}</span>{selected === model.id && view === 'compare' && <span className="selection-dot" />}
        </button>)}
      {search.trim() && !matched.length && <p className="sidebar-empty">No reviewed models match.</p>}
      <button className="text-link sidebar-explore" onClick={() => onView('models')}>Explore all {models.length} models <ArrowUpRight size={13} /></button>
    </div>
    <div className="sidebar-bottom"><div className="mission-card"><ShieldCheck size={20} /><strong>Just prices. No routing.</strong><p>Independent observations.<br />Official sources. Open data.</p><button onClick={() => onView('methodology')}>How we track <ArrowUpRight size={14} /></button></div><div className="sidebar-footer"><span className="live-dot" /> OFFICIAL SOURCE DATA <span>NATIVE</span></div></div>
  </aside>;
}
