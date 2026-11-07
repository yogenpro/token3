import { useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import { comparisonsPaused, weightLabel, type Dataset } from '../lib/data';
import { defaultWorkload, money, quoteUnit, rankOfferings, unitLabel } from '../lib/pricing';
import { ModelMark, ProviderMark } from './UI';
import type { CatalogIndex } from '../lib/catalog';
import { CollectedModels } from './CollectedModels';

export function Explorer({ data, onModel, catalog, directory, onDirectory, onProvider }: { data: Dataset; onModel: (id: string) => void; catalog?: CatalogIndex; directory: string; onDirectory: (mode: string) => void; onProvider: (provider: string, record?: string) => void }) {
  const [search, setSearch] = useState('');
  const [creator, setCreator] = useState('all');
  const [provider, setProvider] = useState('all');
  const [family, setFamily] = useState('all');
  const [weights, setWeights] = useState('all');
  const [depth, setDepth] = useState('all');
  const models = data.models.filter((m) => {
    const activeOffers = data.offerings.filter((o) => o.active && !comparisonsPaused(o.provider) && o.model_id === m.id);
    const providerSet = new Set(activeOffers.map((o) => o.provider));
    const matchesWeights = weights === 'all' || (weights === 'open' && m.open_weight === true) || (weights === 'closed' && m.open_weight === false) || (weights === 'unverified' && m.open_weight === null);
    const matchesDepth = depth === 'all' || (depth === 'multi' && providerSet.size >= 2) || (depth === 'single' && providerSet.size === 1);
    return (creator === 'all' || m.creator === creator) && (family === 'all' || m.family === family) &&
      matchesWeights && matchesDepth &&
      (provider === 'all' || activeOffers.some((o) => o.provider === provider)) &&
      `${m.name} ${m.creator} ${m.family} ${m.version} ${m.id}`.toLowerCase().includes(search.trim().toLowerCase());
  });
  return <><div className="page-heading"><div className="eyebrow">YOUR MODEL, ACROSS THE MARKET</div><h1>Find a model. <span>Know the offering.</span></h1><p>Reviewed comparisons and broader source listings, with exact identities and commercial differences kept separate.</p></div>
    <div className="segments catalog-tabs" role="group" aria-label="Model directory"><button aria-label="Reviewed models" className={directory === 'reviewed' ? 'active' : ''} aria-pressed={directory === 'reviewed'} onClick={() => onDirectory('reviewed')}>Reviewed models <span className="tab-count">{data.models.length}</span></button><button aria-label="Collected listings" className={directory === 'collected' ? 'active' : ''} aria-pressed={directory === 'collected'} onClick={() => onDirectory('collected')}>Collected listings {catalog && <span className="tab-count">{catalog.coverage.model_listing_count.toLocaleString('en-US')}</span>}</button></div>
    {directory === 'collected' ? catalog ? <CollectedModels catalog={catalog} onProvider={onProvider} /> : <div className="catalog-loading" role="status">Waiting for catalog index…</div> : <><div className="explorer-summary"><span><strong>{data.models.length}</strong> canonical models</span><span><strong>{new Set(data.offerings.filter((o) => o.active && !comparisonsPaused(o.provider)).map((o) => o.provider)).size}</strong> providers</span><span><strong>{data.offerings.filter((o) => o.active && !comparisonsPaused(o.provider)).length}</strong> current unpaused reviewed offerings across all tiers</span></div>
    <div className="catalog-toolbar"><select aria-label="Filter reviewed models by creator" value={creator} onChange={(e) => setCreator(e.target.value)}><option value="all">All creators</option>{[...new Set(data.models.map((m) => m.creator))].sort().map((c) => <option key={c}>{c}</option>)}</select><select aria-label="Filter reviewed models by family" value={family} onChange={(e) => setFamily(e.target.value)}><option value="all">All model families</option>{[...new Set(data.models.map((m) => m.family))].sort().map((f) => <option key={f}>{f}</option>)}</select><select aria-label="Filter reviewed models by billing provider" value={provider} onChange={(e) => setProvider(e.target.value)}><option value="all">All billing providers</option>{catalog?.providers.filter((p) => data.offerings.some((o) => o.active && !comparisonsPaused(o.provider) && o.provider === p.id)).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select><select aria-label="Filter reviewed models by weight access" value={weights} onChange={(e) => setWeights(e.target.value)}><option value="all">All weight access</option><option value="open">Open weights</option><option value="closed">Proprietary</option><option value="unverified">Weights unverified</option></select><select aria-label="Filter reviewed models by provider depth" value={depth} onChange={(e) => setDepth(e.target.value)}><option value="all">All provider depths</option><option value="multi">Multi-provider (2+)</option><option value="single">Single billing source</option></select></div>
    <section className="panel explorer-panel"><div className="section-heading"><div><h2>Model explorer <span className="count-badge">{models.length}</span></h2><p>Lowest input and output may come from different offerings. USD Standard tier, using the default workload’s prompt band and DeepSeek peak scenario. Other billing bases are available in Compare.</p></div><label className="search-field"><Search size={16} /><input aria-label="Search models" placeholder="Search models…" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div><div className="table-scroll"><table className="explorer-table"><thead><tr><th>Canonical model</th><th>Providers</th><th>Lowest input / 1M</th><th>Lowest output / 1M</th><th>Input spread</th><th /></tr></thead><tbody>{models.map((model) => {
      const ranked = rankOfferings(data, model.id, defaultWorkload).filter((row) => row.cost.eligible);
      const providers = [...new Set(ranked.map((r) => r.offering.provider))];
      const otherBases = [...new Set(data.offerings.filter((o) => o.active && !comparisonsPaused(o.provider) && o.model_id === model.id).map((o) => quoteUnit(o)).filter((u) => u !== 'USD'))];
      const input = Math.min(...ranked.map((r) => r.price.input_per_million));
      const output = Math.min(...ranked.map((r) => r.price.output_per_million));
      const max = Math.max(...ranked.map((r) => r.price.input_per_million));
      return <tr key={model.id}><td><div className="explorer-model"><ModelMark model={model} /><div><button onClick={() => onModel(model.id)}>{model.name} <ArrowRight size={14} /></button><small title={model.description}>{model.creator} · {model.version} · {weightLabel(model)}{model.lifecycle === 'legacy' ? ' · legacy' : ''}</small><div className="explorer-model-ids"><code>{model.id}</code>{otherBases.map((b) => <span key={b} className="subtle-badge">+ {unitLabel(b)}</span>)}</div></div></div></td><td><div className="provider-stack">{providers.map((p) => <ProviderMark provider={p} key={p} />)}<span>{providers.length}</span></div><small>{providers.length === 1 ? 'Single billing source' : `${providers.length} billing sources`}</small></td><td className="price-cell">{ranked.length ? money(input) : '—'}</td><td className="price-cell">{ranked.length ? money(output) : '—'}</td><td><span className="spread-badge">{ranked.length && input > 0 ? `${(max / input).toFixed(1)}×` : '—'}</span></td><td><button className="icon-button" aria-label={`Compare ${model.name}`} onClick={() => onModel(model.id)}><ArrowRight size={17} /></button></td></tr>;
    })}</tbody></table></div>{!models.length && <div className="empty-state"><Search size={28} /><h3>No matching models</h3><p>Try a model family or creator, such as Llama, Qwen, or OpenAI.</p></div>}</section></>}</>;
}
