import { ArrowDownRight, ArrowRight, ArrowUpRight, CirclePlus, Info, Minus, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import type { Change, Dataset } from '../lib/data';
import { providerInfo } from '../lib/data';
import { dateLabel, exactDate, money, tokens } from '../lib/pricing';

const fields: Record<string, string> = { input_per_million: 'input', output_per_million: 'output', cache_read_per_million: 'cache read', cache_write_per_million: 'cache write', context_window: 'context window', quantization: 'precision', variant: 'variant', max_output_tokens: 'output limit' };
export function movement(change: Change) {
  if (change.kind !== 'price_changed' || typeof change.old !== 'number' || typeof change.new !== 'number') return 'other';
  return change.new < change.old ? 'cut' : 'increase';
}
function title(change: Change) {
  const field = fields[change.field ?? ''] ?? change.field;
  if (change.kind === 'offering_added') return 'Added to tracking';
  if (change.kind === 'offering_removed') return 'Offering no longer listed';
  if (change.kind === 'offering_restored') return 'Offering relisted';
  if (change.kind === 'offering_updated') return `${field} updated`;
  if (change.old === null) return `${field} price published`;
  if (change.new === null) return `${field} price no longer published`;
  return `${field} price ${movement(change) === 'cut' ? 'decreased' : 'increased'}`;
}
function changeValue(value: Change['old'], change: Change) {
  if (value === null) return '—';
  if (change.kind === 'price_changed' && typeof value === 'number') return money(value);
  if (change.field === 'context_window' && typeof value === 'number') return tokens(value);
  return String(value);
}
export function ChangeItem({ change, data, compact = false }: { change: Change; data: Dataset; compact?: boolean }) {
  const model = data.models.find((m) => m.id === change.model_id)!;
  const offering = data.offerings.find((o) => o.id === change.offering_id)!;
  const direction = movement(change);
  const Icon = change.kind === 'offering_added' ? CirclePlus : change.kind === 'offering_removed' ? Minus : change.kind === 'offering_restored' ? RefreshCw : direction === 'cut' ? ArrowDownRight : direction === 'increase' ? ArrowUpRight : Info;
  return <article className={`change-item ${compact ? 'compact' : ''}`}>
    <div className={`change-icon ${direction}`}><Icon size={17} /></div>
    <div className="change-content"><div className="change-top"><strong>{providerInfo(change.provider).name}</strong><time dateTime={change.observed_at} title={exactDate(change.observed_at)}>{dateLabel(change.observed_at)}</time></div>
      <p>{title(change)}</p><div className="change-model">{model.name}{!compact && ` · ${offering.service_tier}${offering.variant !== 'standard' ? ` · ${offering.variant}` : ''}${offering.region !== 'unspecified' ? ` · ${offering.region}` : ''}`}</div>
      {change.field && <div className={`change-values ${direction}`}><span>{changeValue(change.old, change)}</span><ArrowRight size={13} /><strong>{changeValue(change.new, change)}</strong>{change.change_pct !== null && <span className="change-pct">{change.change_pct > 0 ? '+' : ''}{Number(change.change_pct.toFixed(1))}%</span>}</div>}
      {!compact && change.kind === 'offering_added' && <p className="change-explanation">First seen in our dataset, not a claim about the provider’s launch date.</p>}
      {!compact && <a className="text-link" href={offering.source_url} target="_blank" rel="noopener noreferrer">Official source <ArrowUpRight size={13} /></a>}
    </div>
  </article>;
}
export function RecentMovements({ data, onAll }: { data: Dataset; onAll: () => void }) {
  const priceChanges = data.changes.filter((c) => c.kind === 'price_changed');
  const items = (priceChanges.length ? priceChanges : data.changes).slice(0, 3);
  return <section className="panel movements-panel"><div className="section-heading"><div><div className="eyebrow">THE WATCH FEED</div><h2>Latest movements</h2></div><span className="subtle-badge">{priceChanges.length ? 'Price changes' : 'First observations'}</span></div>
    <div className="movements-list">{items.length ? items.map((item) => <ChangeItem key={item.id} change={item} data={data} compact />) : <div className="empty-small">No changes observed yet.</div>}</div>
    <button className="feed-link" onClick={onAll}>Explore all observations <ArrowRight size={16} /></button>
  </section>;
}
export function ChangesView({ data }: { data: Dataset }) {
  const [filter, setFilter] = useState('all');
  const [model, setModel] = useState('all');
  const [limit, setLimit] = useState(20);
  const changes = data.changes.filter((c) => (model === 'all' || c.model_id === model) && (filter === 'all' || (filter === 'availability' ? c.kind !== 'price_changed' : movement(c) === filter)));
  const verified = data.changes.filter((c) => c.kind === 'price_changed').length;
  return <><div className="page-heading"><div className="eyebrow">FOLLOW THE MARKET</div><h1>A record of what changed.</h1><p>Price changes, offering updates, and new discoveries. Every event starts with an observation.</p></div>
    <div className="notice"><Info size={17} /><span>{verified === 0 ? 'Tracking has just started. There are no verified price changes yet. The entries below are real first observations, not historical launch dates.' : `${verified} verified price changes recorded. Discovery dates are not model launch dates.`}</span></div>
    <section className="panel changes-panel"><div className="changes-toolbar"><div className="segments" role="group" aria-label="Change type">{[['all', 'All events'], ['cut', 'Price cuts'], ['increase', 'Price increases'], ['availability', 'Offerings']].map(([value, label]) => <button className={filter === value ? 'active' : ''} key={value} onClick={() => { setFilter(value); setLimit(20); }}>{label}</button>)}</div>
      <select aria-label="Filter changes by model" value={model} onChange={(e) => { setModel(e.target.value); setLimit(20); }}><option value="all">All models</option>{data.models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
    </div><div className="event-count">{changes.length} {changes.length === 1 ? 'event' : 'events'} · timestamps in UTC</div>
      {changes.length ? <div className="full-feed">{changes.slice(0, limit).map((change) => <ChangeItem key={change.id} change={change} data={data} />)}</div> : <div className="empty-state"><RefreshCw size={28} /><h3>No matching changes yet</h3><p>New observations are collected daily. Try another filter, or check back after the next collection.</p></div>}
      {changes.length > limit && <button className="button load-more" onClick={() => setLimit(limit + 20)}>Show more events</button>}
    </section></>;
}
