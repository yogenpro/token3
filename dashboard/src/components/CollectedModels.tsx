import { useMemo, useState } from 'react';
import { ArrowRight, Info, Search } from 'lucide-react';
import type { z } from 'zod';
import type { CatalogIndex } from '../lib/catalog';
import { billingBases, kindLabel, modelDirectorySchema, modelListingsSchema, summarySearch } from '../lib/catalog';
import { useCatalogChunks } from '../lib/catalogChunks';
import { providerInfo } from '../lib/data';
import { useCatalogAsset } from '../lib/useCatalogAsset';
import { ProviderMark } from './UI';
import { AssetNotice, Pager } from './CatalogUI';

const listingRows = (value: z.infer<typeof modelListingsSchema>) => value.listings;

export function CollectedModels({ catalog, onProvider }: { catalog: CatalogIndex; onProvider: (provider: string, record?: string) => void }) {
  const asset = useCatalogAsset('catalog/models.json', modelDirectorySchema, catalog.updated_at);
  const chunks = useCatalogChunks(asset.data?.chunks, modelListingsSchema, listingRows, catalog.updated_at);
  const [search, setSearch] = useState('');
  const [provider, setProvider] = useState('all');
  const [modality, setModality] = useState('all');
  const [page, setPage] = useState(1);
  const [basis, setBasis] = useState('all');
  const [pricing, setPricing] = useState('all');
  const valid = chunks.data && chunks.data.length === catalog.coverage.model_listing_count && chunks.data.every((r) => catalog.providers.some((p) => p.id === r.provider));
  const listings = valid ? chunks.data : undefined;
  const filtered = useMemo(() => listings?.filter((r) => (provider === 'all' || r.provider === provider) &&
    (modality === 'all' || r.modalities.includes(modality)) && (basis === 'all' || r.billing_basis === basis) &&
    (pricing === 'all' || r.pricing_state === pricing) && `${summarySearch(r)} ${providerInfo(r.provider).name.toLowerCase()}`.includes(search.trim().toLowerCase())) ?? [], [listings, search, provider, modality, basis, pricing]);
  const update = (set: (value: string) => void, value: string) => { set(value); setPage(1); };
  const current = Math.min(page, Math.max(1, Math.ceil(filtered.length / 25)));
  return <><div className="notice"><Info size={17} /><span>These are named API model, route, and flavor listings—not deduplicated canonical models. Similar names do not establish equivalence. Pricing documents, cloud meters, and SKUs are searchable in Providers.</span></div><AssetNotice loading={asset.loading} error={asset.error} retry={asset.retry} /><AssetNotice loading={chunks.loading} error={chunks.error ?? (chunks.data && !valid ? 'Model directory and coverage index differ.' : undefined)} retry={chunks.retry} />{listings && <section className="panel collected-models"><div className="section-heading"><div><h2>Collected model listings <span className="count-badge">{listings.length.toLocaleString('en-US')}</span></h2><p>Discover the broader market. Native billing stays separate from reviewed comparisons.</p></div></div><div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search collected models" placeholder="Model name, native ID, provider, or route…" value={search} onChange={(e) => update(setSearch, e.target.value)} /></label><select aria-label="Filter collected models by provider" value={provider} onChange={(e) => update(setProvider, e.target.value)}><option value="all">All providers</option>{catalog.providers.filter((p) => p.model_listing_count).map((p) => <option value={p.id} key={p.id}>{p.name}</option>)}</select><select aria-label="Filter collected models by modality" value={modality} onChange={(e) => update(setModality, e.target.value)}><option value="all">All published modalities</option>{[...new Set(listings.flatMap((r) => r.modalities))].sort().map((m) => <option key={m}>{m}</option>)}</select><select aria-label="Filter collected models by billing basis" value={basis} onChange={(e) => update(setBasis, e.target.value)}><option value="all">All billing bases</option>{billingBases.map((b) => <option key={b}>{b}</option>)}</select><select aria-label="Filter collected models by pricing state" value={pricing} onChange={(e) => update(setPricing, e.target.value)}><option value="all">All pricing states</option>{[...new Set(listings.map((r) => r.pricing_state))].sort().map((p) => <option key={p}>{p}</option>)}</select></div><div className="table-scroll"><table className="native-table"><thead><tr><th>Source model identity</th><th>Commercial source</th><th>Native billing</th><th>Review</th><th>Details</th></tr></thead><tbody>{filtered.slice((current - 1) * 25, current * 25).map((r) => <tr key={r.id}><td><strong>{r.label}</strong><code>{r.native_id}</code><small>{r.modalities.length ? r.modalities.join(' · ') : 'Modalities not published'}</small></td><td><div className="provider-cell"><ProviderMark provider={r.provider} /><strong>{providerInfo(r.provider).name}</strong></div><small>{catalog.providers.find((p) => p.id === r.provider)?.access} · {kindLabel(r.kind)}</small><small>{r.scope_label || 'No additional source scope published'}</small></td><td>{r.pricing_state}<small>{r.billing_basis}</small></td><td><span className="subtle-badge">Not compared</span><small>{r.reviewed_model_ids.length ? 'Reviewed model identity linked' : 'Identity review pending'}</small></td><td><button className="text-link" aria-label={`Explore collected listing ${r.native_id} on ${providerInfo(r.provider).name}`} onClick={() => onProvider(r.provider, r.id)}>Explore <ArrowRight size={14} /></button></td></tr>)}</tbody></table></div>{!filtered.length && <div className="empty-state"><h3>No matching collected listings</h3><p>Try a different model, provider, or modality. Document-only listings are in Providers.</p></div>}<Pager page={current} total={filtered.length} onPage={setPage} /></section>}</>;
}
