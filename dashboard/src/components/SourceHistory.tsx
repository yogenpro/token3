import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Search } from 'lucide-react';
import type { z } from 'zod';
import { historyManifestSchema, nativeChangesSchema, type CatalogIndex, type NativeChange } from '../lib/catalog';
import { pageChunks, useCatalogChunks } from '../lib/catalogChunks';
import { providerInfo } from '../lib/data';
import { dateLabel, exactDate } from '../lib/pricing';
import { AssetNotice, NativeEvent, Pager } from './CatalogUI';

const eventRows = (value: z.infer<typeof nativeChangesSchema>) => value.events;
const categoryName = { price: 'Native amount', rule: 'Billing rule', catalog: 'Catalog' };

export function SourceHistory({ manifest, version, onProvider, catalog, recordId = '', providerOnly = false }: {
  manifest: z.infer<typeof historyManifestSchema>; version: string; onProvider: (id: string, record?: string) => void;
  catalog?: CatalogIndex; recordId?: string; providerOnly?: boolean;
}) {
  const [provider, setProvider] = useState('all');
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [batchId, setBatchId] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => { setBatchId(''); setPage(1); }, [version, recordId, provider, category]);
  const batches = useMemo(() => manifest.batches.filter((b) => (provider === 'all' || b.provider === provider) &&
    (category === 'all' || b.category === category)), [manifest, provider, category]);
  const selected = batches.find((b) => b.id === batchId);
  const fullSearch = !!query || !!recordId;
  const total = selected?.event_count ?? 0;
  const eventPage = Math.min(page, Math.max(1, Math.ceil(total / 25)));
  const slice = selected ? pageChunks(selected.chunks, eventPage) : undefined;
  const refs = fullSearch ? batches.flatMap((b) => b.chunks) : slice?.refs;
  const rows = useCatalogChunks(refs, nativeChangesSchema, eventRows, version);
  const matched = useMemo(() => rows.data?.filter((e) => (!recordId || e.record_id === recordId) &&
    (!query || `${e.label} ${e.title} ${providerInfo(e.provider).name}`.toLowerCase().includes(query))) ?? [], [rows.data, recordId, query]);
  const resultPage = Math.min(page, Math.max(1, Math.ceil(matched.length / 25)));
  const visible = fullSearch ? matched.slice((resultPage - 1) * 25, resultPage * 25) : rows.data?.slice(slice?.offset ?? 0, (slice?.offset ?? 0) + 25);
  const batchPage = Math.min(page, Math.max(1, Math.ceil(batches.length / 25)));
  const count = batches.reduce((n, b) => n + b.event_count, 0);
  return <>
    <form className="catalog-toolbar" onSubmit={(e) => { e.preventDefault(); setQuery(search.trim().toLowerCase()); setBatchId(''); setPage(1); }}>
      <label className="search-field"><Search size={16} /><input aria-label="Search native changes" placeholder="Search all retained event labels…" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <button className="button" type="submit">Search all observations</button>
      {catalog && <select aria-label="Filter native changes by provider" value={provider} onChange={(e) => setProvider(e.target.value)}><option value="all">All providers</option>{catalog.providers.map((p) => <option value={p.id} key={p.id}>{p.name}</option>)}</select>}
      {providerOnly && <select aria-label="Filter provider history" value={category} onChange={(e) => setCategory(e.target.value)}><option value="all">All source events</option><option value="price">Native price amounts</option><option value="rule">Billing rules</option><option value="catalog">Catalog changes</option></select>}
    </form>
    {(selected || fullSearch) ? <>
      <button className="text-link catalog-back" onClick={() => { setBatchId(''); setQuery(''); setSearch(''); setPage(1); }} disabled={!!recordId}><ArrowLeft size={15} /> Observation batches</button>
      <p className="history-selection">{fullSearch ? recordId ? 'Finding this record across all retained event chunks.' : 'Searching all matching observation batches; results are complete, not limited to a visible page.' : `${providerInfo(selected!.provider).name} · ${categoryName[selected!.category]} · ${exactDate(selected!.observed_at)}`}</p>
      {rows.loading && <p className="catalog-loading" role="status">{fullSearch ? 'Searching retained history' : 'Loading event page'}… {rows.progress.done} / {rows.progress.total} chunks</p>}
      <AssetNotice loading={false} error={rows.error} retry={rows.retry} />
      {rows.data && <><div className="full-feed">{visible?.map((event: NativeChange) => <NativeEvent key={event.id} event={event} onRecord={onProvider} />)}</div>
        {!visible?.length && <div className="empty-state"><h3>No matching source events</h3><p>No retained observations match this selection. Source absence is not discontinuation.</p></div>}
        <Pager page={fullSearch ? resultPage : eventPage} total={fullSearch ? matched.length : total} onPage={setPage} /></>}
    </> : <>
      <p className="history-selection">{count.toLocaleString('en-US')} events in {batches.length.toLocaleString('en-US')} observation batches · UTC. Open a batch to load event pages.</p>
      <div className="history-batches">{batches.slice((batchPage - 1) * 25, batchPage * 25).map((batch) => <article className="history-batch" key={batch.id}>
        <div><strong>{providerInfo(batch.provider).name}</strong><time dateTime={batch.observed_at} title={exactDate(batch.observed_at)}>{dateLabel(batch.observed_at, true)}</time><span>{categoryName[batch.category]} observations · {batch.event_count.toLocaleString('en-US')} events</span></div>
        <button className="text-link" aria-label={`Open ${batch.provider} ${batch.category} observation batch ${batch.observed_at}`} onClick={() => { setBatchId(batch.id); setPage(1); }}>View events <ArrowRight size={14} /></button>
      </article>)}</div>
      {!batches.length && <div className="empty-state"><h3>No matching source events</h3><p>No recorded observations in this selection.</p></div>}
      <Pager page={batchPage} total={batches.length} onPage={setPage} />
    </>}
  </>;
}
