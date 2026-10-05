import { useState } from 'react';
import { ArrowRight, Search } from 'lucide-react';
import type { Dataset } from '../lib/data';
import { defaultWorkload, money, rankOfferings } from '../lib/pricing';
import { ModelMark, ProviderMark } from './UI';

export function Explorer({ data, onModel }: { data: Dataset; onModel: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const models = data.models.filter((m) => `${m.name} ${m.creator} ${m.family} ${m.version}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <><div className="page-heading"><div className="eyebrow">YOUR MODEL, ACROSS THE MARKET</div><h1>A small catalog. <span>A clearer picture.</span></h1><p>Open and proprietary models across specialized APIs and major clouds. Exact releases and offering differences stay visible.</p></div>
    <div className="explorer-summary"><span><strong>{data.models.length}</strong> canonical models</span><span><strong>{new Set(data.offerings.filter((o) => o.active).map((o) => o.provider)).size}</strong> providers</span><span><strong>{data.offerings.filter((o) => o.active).length}</strong> tracked offerings across all tiers</span></div>
    <section className="panel explorer-panel"><div className="section-heading"><div><h2>Model explorer</h2><p>Lowest input and output may come from different offerings. Standard tier, using the default workload’s prompt band.</p></div><label className="search-field"><Search size={16} /><input aria-label="Search models" placeholder="Search models…" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div><div className="table-scroll"><table className="explorer-table"><thead><tr><th>Canonical model</th><th>Providers</th><th>Lowest input / 1M</th><th>Lowest output / 1M</th><th>Input spread</th><th /></tr></thead><tbody>{models.map((model) => {
      const ranked = rankOfferings(data, model.id, defaultWorkload).filter((row) => row.cost.eligible);
      const providers = [...new Set(ranked.map((r) => r.offering.provider))];
      const input = Math.min(...ranked.map((r) => r.price.input_per_million));
      const output = Math.min(...ranked.map((r) => r.price.output_per_million));
      const max = Math.max(...ranked.map((r) => r.price.input_per_million));
      return <tr key={model.id}><td><div className="explorer-model"><ModelMark model={model} /><div><button onClick={() => onModel(model.id)}>{model.name} <ArrowRight size={14} /></button><small title={model.description}>{model.creator} · {model.version} · {model.open_weight ? 'open weights' : 'proprietary'}{model.lifecycle === 'legacy' ? ' · legacy' : ''}</small><code>{model.id}</code></div></div></td><td><div className="provider-stack">{providers.map((p) => <ProviderMark provider={p} key={p} />)}<span>{providers.length}</span></div></td><td className="price-cell">{ranked.length ? money(input) : '—'}</td><td className="price-cell">{ranked.length ? money(output) : '—'}</td><td><span className="spread-badge">{ranked.length && input > 0 ? `${(max / input).toFixed(1)}×` : '—'}</span></td><td><button className="icon-button" aria-label={`Compare ${model.name}`} onClick={() => onModel(model.id)}><ArrowRight size={17} /></button></td></tr>;
    })}</tbody></table></div>{!models.length && <div className="empty-state"><Search size={28} /><h3>No matching models</h3><p>Try a model family or creator, such as Llama, Qwen, or OpenAI.</p></div>}</section></>;
}
