import { useEffect, useState } from 'react';
import { Activity, Archive, ArrowUpRight, ChartNoAxesCombined, CircleHelp, Grid2X2, Building2, Layers, Search, ShieldCheck } from 'lucide-react';
import type { Model } from '../lib/data';
import { Brand, ModelMark } from './UI';
export type View = 'compare' | 'models' | 'providers' | 'changes' | 'historical' | 'coverage' | 'methodology';
const navGroups = [
  {
    heading: 'REVIEWED LAYER',
    items: [
      { id: 'compare', label: 'Compare prices', icon: ChartNoAxesCombined },
      { id: 'models', label: 'Model explorer', icon: Grid2X2 },
    ],
  },
  {
    heading: 'SOURCE WAREHOUSE',
    items: [
      { id: 'providers', label: 'Providers', icon: Building2 },
      { id: 'changes', label: 'Recent changes', icon: Activity },
      { id: 'historical', label: 'Historical evidence', icon: Archive },
    ],
  },
  {
    heading: 'PIPELINE & AUDIT',
    items: [
      { id: 'coverage', label: 'Coverage', icon: Layers },
      { id: 'methodology', label: 'Methodology', icon: CircleHelp },
    ],
  },
] as const;
const storageKey = 'tokentokentoken-recent-models';
function savedRecent(): string[] {
  try { const value: unknown = JSON.parse(localStorage.getItem(storageKey) ?? '[]'); return Array.isArray(value) ? value.filter((id) => typeof id === 'string').slice(0, 6) : []; }
  catch { return []; }
}

export function Sidebar({ models, selected, view, onView, onModel, changeCount, providerCount = 0 }: { models: Model[]; selected: string; view: View; onView: (view: View) => void; onModel: (id: string) => void; changeCount: number; providerCount?: number }) {
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
    <nav className="main-nav" aria-label="Main navigation">{navGroups.map((group) => <div className="nav-group" key={group.heading}>
      <div className="nav-group-label" aria-hidden="true">{group.heading}</div>
      {group.items.map(({ id, label, icon: Icon }) =>
        <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => onView(id)} aria-label={label} aria-description={id === 'changes' && changeCount > 0 ? `${changeCount} verified price changes recorded` : undefined} aria-current={view === id ? 'page' : undefined}>
          <Icon size={16} strokeWidth={1.9} /><span>{label}</span>
          {id === 'changes' && changeCount > 0 && <span className="nav-count">{changeCount}</span>}
          {id === 'models' && models.length > 0 && <span className="nav-count">{models.length}</span>}
          {id === 'providers' && providerCount > 0 && <span className="nav-count">{providerCount}</span>}
        </button>)}
    </div>)}</nav>
    <div className="watchlist"><label className="search-field sidebar-search"><Search size={14} /><input aria-label="Search reviewed models" placeholder="Quick-switch model…" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <div className="sidebar-label">{search.trim() ? 'MATCHING MODELS' : 'RECENT MODELS'} <span>{matched.length}</span></div>{matched.slice(0, 6).map((model) =>
        <button key={model.id} className={`watch-item ${selected === model.id && view === 'compare' ? 'selected' : ''}`} onClick={() => { onModel(model.id); setSearch(''); }}>
          <ModelMark model={model} small /><span className="watch-item-text"><span>{model.name}</span><small>{model.creator}</small></span>{selected === model.id && view === 'compare' && <span className="selection-dot" />}
        </button>)}
      {search.trim() && !matched.length && <p className="sidebar-empty">No reviewed models match.</p>}
      <button className="text-link sidebar-explore" onClick={() => onView('models')}>Explore all {models.length} models <ArrowUpRight size={13} /></button>
    </div>
    <div className="sidebar-bottom"><div className="mission-card"><ShieldCheck size={18} /><strong>3-Layer Price Ledger</strong><p>Reviewed quotes · Native warehouse · Historical archive.</p><button onClick={() => onView('methodology')}>How we track <ArrowUpRight size={13} /></button></div><div className="sidebar-footer"><span className="live-dot" /> STATIC · READ-ONLY <span>OPEN DATA</span></div></div>
  </aside>;
}
