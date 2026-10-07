import { useMemo, useState } from 'react';
import { Info, Search } from 'lucide-react';
import { nativeChangesSchema, type CatalogIndex, type ChangeCategory } from '../lib/catalog';
import { providerInfo } from '../lib/data';
import { useCatalogAsset } from '../lib/useCatalogAsset';
import { AssetNotice, NativeEvent, Pager } from './CatalogUI';

export function NativeChanges({ catalog, category, onProvider }: { catalog: CatalogIndex; category: ChangeCategory; onProvider: (provider: string, record?: string) => void }) {
  const asset = useCatalogAsset(`catalog/changes/${category}.json`, nativeChangesSchema, catalog.updated_at);
  const [search, setSearch] = useState('');
  const [provider, setProvider] = useState('all');
  const [page, setPage] = useState(1);
  const events = asset.data?.events;
  const filtered = useMemo(() => events?.filter((e) => (provider === 'all' || e.provider === provider) && `${e.label} ${e.title} ${providerInfo(e.provider).name}`.toLowerCase().includes(search.trim().toLowerCase())) ?? [], [events, search, provider]);
  const current = Math.min(page, Math.max(1, Math.ceil(filtered.length / 25)));
  return <><div className="notice"><Info size={17} /><span>{category === 'price' ? 'Native amount changes use the same explicit currency, unit, conditions, and scope. They are not reviewed model comparisons. Gateway changes describe advertised catalog prices, not a guaranteed selected supplier.' : category === 'rule' ? 'Billing formulas, units, currencies, conditions, and guide revisions. First-captured guides are observations, not historical price changes.' : 'Real discoveries, source absences, reappearances, and metadata changes. Discovery dates are not launch dates; source absence does not prove discontinuation.'}</span></div><AssetNotice loading={asset.loading} error={asset.error} retry={asset.retry} />{events && <section className="panel changes-panel"><div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search native changes" placeholder="Listing, provider, or event…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></label><select aria-label="Filter native changes by provider" value={provider} onChange={(e) => { setProvider(e.target.value); setPage(1); }}><option value="all">All providers</option>{catalog.providers.map((p) => <option value={p.id} key={p.id}>{p.name}</option>)}</select><span>{filtered.length.toLocaleString('en-US')} events · UTC</span></div><div className="full-feed">{filtered.slice((current - 1) * 25, current * 25).map((event) => <NativeEvent key={event.id} event={event} onRecord={onProvider} />)}</div>{!filtered.length && <div className="empty-state"><h3>No matching native changes</h3><p>No recorded events match this source and category.</p></div>}<Pager page={current} total={filtered.length} onPage={setPage} /></section>}</>;
}
