import { Activity, ArrowUpRight, ChartNoAxesCombined, CircleHelp, Grid2X2, ShieldCheck } from 'lucide-react';
import type { Model } from '../lib/data';
import { Brand, ModelMark } from './UI';
export type View = 'compare' | 'models' | 'changes' | 'methodology';
const navigation = [
  { id: 'compare', label: 'Compare prices', icon: ChartNoAxesCombined },
  { id: 'models', label: 'Model explorer', icon: Grid2X2 },
  { id: 'changes', label: 'Recent changes', icon: Activity },
  { id: 'methodology', label: 'Methodology', icon: CircleHelp },
] as const;

export function Sidebar({ models, selected, view, onView, onModel, changeCount }: { models: Model[]; selected: string; view: View; onView: (view: View) => void; onModel: (id: string) => void; changeCount: number }) {
  return <aside className="sidebar">
    <Brand />
    <nav className="main-nav" aria-label="Main navigation">{navigation.map(({ id, label, icon: Icon }) =>
      <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => onView(id)} aria-label={label} aria-description={id === 'changes' && changeCount > 0 ? `${changeCount} verified price changes recorded` : undefined} aria-current={view === id ? 'page' : undefined}>
        <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{id === 'changes' && changeCount > 0 && <span className="nav-count">{changeCount}</span>}
      </button>)}
    </nav>
    <div className="watchlist"><div className="sidebar-label">WATCHLIST <span>{models.length}</span></div>{models.map((model) =>
      <button key={model.id} className={`watch-item ${selected === model.id && view === 'compare' ? 'selected' : ''}`} onClick={() => onModel(model.id)}>
        <ModelMark model={model} small /><span>{model.name}</span>{selected === model.id && view === 'compare' && <span className="selection-dot" />}
      </button>)}
    </div>
    <div className="sidebar-bottom"><div className="mission-card"><ShieldCheck size={20} /><strong>Just prices. No routing.</strong><p>Independent observations.<br />Official sources. Open data.</p><button onClick={() => onView('methodology')}>How we track <ArrowUpRight size={14} /></button></div><div className="sidebar-footer"><span className="live-dot" /> PUBLIC LIST PRICES <span>USD</span></div></div>
  </aside>;
}
