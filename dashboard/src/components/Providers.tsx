import { useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUpRight, Download, Info, Search } from 'lucide-react';
import type { z } from 'zod';
import type { Dataset } from '../lib/data';
import { accessKinds, billingBases, historyManifestSchema, jsonText, kindLabel, nativeRateText, pricingState, providerCatalogSchema,
  recordChunkSchema, recordIndexChunkSchema, scopeLabel, sourceFreshness, summarySearch,
  type CatalogIndex, type CatalogProvider, type NativeRecord } from '../lib/catalog';
import { loadCatalogRows, useCatalogChunks } from '../lib/catalogChunks';
import { useCatalogAsset } from '../lib/useCatalogAsset';
import { dateLabel, downloadFile, exactDate } from '../lib/pricing';
import { ProviderMark } from './UI';
import { AssetNotice, Pager } from './CatalogUI';
import { SourceHistory } from './SourceHistory';

const indexRows = (value: z.infer<typeof recordIndexChunkSchema>) => value.records;
const recordRows = (value: z.infer<typeof recordChunkSchema>) => value.records;

export function Providers({ data, catalog, providerId, recordId, onProvider, onModel }: { data: Dataset; catalog: CatalogIndex; providerId: string; recordId: string; onProvider: (id: string, record?: string) => void; onModel: (id: string) => void }) {
  const [search, setSearch] = useState('');
  const [access, setAccess] = useState('all');
  const provider = catalog.providers.find((p) => p.id === providerId);
  if (providerId && !provider) return <div className="empty-state"><h1>Provider not found</h1><p>This provider is not in the published catalog.</p><button className="button" onClick={() => onProvider('')}>All providers</button></div>;
  if (provider) return <ProviderDetail key={provider.id} data={data} provider={provider} version={catalog.updated_at} recordId={recordId} onProvider={onProvider} onModel={onModel} />;
  const visible = catalog.providers.filter((p) => (access === 'all' || p.access === access) && `${p.name} ${p.id}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <><div className="page-heading"><div className="eyebrow">THE SOURCE-NATIVE CATALOG</div><h1>Every source. <span>Its own terms.</span></h1><p>Explore models, routes, billing rules, and cloud meters without forcing them into the same price unit.</p></div>
    <div className="catalog-stats"><div><strong>{catalog.providers.length}</strong><span>provider groups</span></div><div><strong>{catalog.record_count.toLocaleString('en-US')}</strong><span>source records, not unique models</span></div><div><strong>{data.offerings.filter((o) => o.active).length}</strong><span>active reviewed comparison offers</span></div></div>
    <div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search providers" placeholder="Search providers…" value={search} onChange={(e) => setSearch(e.target.value)} /></label><select aria-label="Filter providers by access type" value={access} onChange={(e) => setAccess(e.target.value)}><option value="all">All access types</option>{accessKinds.map((type) => <option key={type}>{type}</option>)}</select></div>
    <div className="provider-grid">{visible.map((p) => {
      const status = data.status.providers.find((s) => s.id === p.id), freshness = sourceFreshness(status);
      const reviewed = data.offerings.filter((o) => o.provider === p.id && o.active).length;
      return <section className="panel provider-card" key={p.id}><div className="provider-card-heading"><ProviderMark provider={p.id} /><div><h2>{p.name}</h2><span className="subtle-badge">{p.access}</span></div></div><span className={`health-badge ${freshness.warning ? 'warning' : ''}`}>{freshness.label}</span><div className="provider-card-counts"><strong>{p.record_count.toLocaleString('en-US')} records</strong><span>{p.model_listing_count.toLocaleString('en-US')} named API listings · {reviewed} active reviewed offers</span></div><p>{Object.entries(p.kind_counts).map(([kind, count]) => `${count.toLocaleString('en-US')} ${kindLabel(kind).toLowerCase()}${count === 1 ? '' : 's'}`).join(' · ')}</p><div className="provider-card-footer"><span title={exactDate(p.last_seen_at)}>Checked {dateLabel(p.last_seen_at, true)}</span><button className="text-link" aria-label={`Explore ${p.name}`} onClick={() => onProvider(p.id)}>Explore <ArrowRight size={15} /></button></div></section>;
    })}</div>
    {!visible.length && <div className="empty-state"><h2>No matching providers</h2><p>Try another provider name or access type.</p></div>}
    <div className="notice"><Info size={17} /><span>Coverage means entries returned by selected official sources, not every region, contract, or account-specific price. Gateways are commercial offers, not inferred upstream endpoints.</span></div>
  </>;
}

function ProviderDetail({ data, provider, version, recordId, onProvider, onModel }: { data: Dataset; provider: CatalogProvider; version: string; recordId: string; onProvider: (id: string, record?: string) => void; onModel: (id: string) => void }) {
  const asset = useCatalogAsset(provider.detail_path, providerCatalogSchema, version);
  const [search, setSearch] = useState(''), [kind, setKind] = useState('all'), [basis, setBasis] = useState('all'), [priceState, setPriceState] = useState('all');
  const [page, setPage] = useState(1), [historyOpen, setHistoryOpen] = useState(false);
  const [exporting, setExporting] = useState(false), [exportError, setExportError] = useState('');
  const history = useCatalogAsset(historyOpen ? provider.history_path : null, historyManifestSchema, version);
  const valid = asset.data?.provider === provider.id && asset.data.catalog_sha256 === provider.catalog_sha256 && asset.data.record_count === provider.record_count;
  const index = useCatalogChunks(valid ? asset.data!.index_chunks : undefined, recordIndexChunkSchema, indexRows, version);
  const records = index.data;
  const indexValid = !!records && records.length === provider.record_count && records.every((r) => r.provider === provider.id && asset.data!.record_chunks.some((c) => c.path === r.detail_path));
  const selected = indexValid ? records.find((r) => r.id === recordId) : undefined;
  const ref = selected && asset.data!.record_chunks.find((c) => c.path === selected.detail_path);
  const detail = useCatalogChunks(ref ? [ref] : undefined, recordChunkSchema, recordRows, version);
  const record = detail.data?.find((r) => r.id === recordId && r.provider === provider.id && r.native_id === selected?.native_id);
  const filtered = useMemo(() => indexValid ? records.filter((r) => (kind === 'all' || r.kind === kind) &&
    (basis === 'all' || r.billing_basis === basis) && (priceState === 'all' || r.pricing_state === priceState) &&
    summarySearch(r).includes(search.trim().toLowerCase())) : [], [records, indexValid, search, kind, basis, priceState]);
  const update = (set: (value: string) => void, value: string) => { set(value); setPage(1); };
  const pageNumber = Math.min(page, Math.max(1, Math.ceil(filtered.length / 25)));
  const status = data.status.providers.find((p) => p.id === provider.id), freshness = sourceFreshness(status);
  const reviewed = data.offerings.filter((o) => o.active && o.provider === provider.id).length;
  const exportRecords = async () => {
    if (!asset.data || !indexValid) return;
    setExporting(true); setExportError('');
    try {
      const paths = new Set(filtered.map((r) => r.detail_path));
      const values = await loadCatalogRows(asset.data.record_chunks.filter((c) => paths.has(c.path)), recordChunkSchema, recordRows);
      const map = new Map(values.map((r) => [r.id, r]));
      const selectedRecords = filtered.map((r) => {
        const value = map.get(r.id);
        if (!value || value.provider !== provider.id || value.native_id !== r.native_id) throw new Error('Export and catalog index differ. Refresh the published dataset.');
        return value;
      });
      downloadFile(JSON.stringify({ provider: provider.id, catalog_sha256: provider.catalog_sha256, records: selectedRecords }, null, 2), `${provider.id}-native-catalog.json`, 'application/json');
    } catch (error) { setExportError(error instanceof Error ? error.message : 'Unable to export the complete selection.'); }
    finally { setExporting(false); }
  };
  return <><button className="text-link catalog-back" onClick={() => onProvider('')}><ArrowLeft size={16} /> All providers</button>
    <div className="page-heading"><div className="eyebrow">{provider.access.toUpperCase()} · SELECTED OFFICIAL SOURCES</div><h1>{provider.name}</h1><p>Browse lightweight indexes. Full native evidence loads only for a selected record or an explicit export.</p></div>
    <div className="catalog-source-summary"><span className={`health-badge ${freshness.warning ? 'warning' : ''}`}>{freshness.label}</span><span>Checked {status?.last_success_at ? <time title={exactDate(status.last_success_at)} dateTime={status.last_success_at}>{dateLabel(status.last_success_at, true)}</time> : 'never successfully'}</span><span>Catalog revision {provider.revision} · changed {dateLabel(provider.changed_at, true)}</span><span>{provider.record_count.toLocaleString('en-US')} records · {reviewed} active reviewed offers</span></div>
    {status?.error && <div className="notice warning" role="alert"><Info size={17} /><span>{status.error} Last good catalog retained.</span></div>}
    {status?.coverage_state === 'limited' && <div className="notice warning"><Info size={17} /><span>Limited coverage: {status.fallback_reason ?? 'Some selected source evidence is unavailable.'}</span></div>}
    <div className="catalog-source-links">{provider.source_urls.map((url) => <a className="text-link" key={url} href={url} target="_blank" rel="noopener noreferrer">Official source: {new URL(url).hostname} <ArrowUpRight size={13} /></a>)}</div>
    <AssetNotice loading={asset.loading} error={asset.error ?? (asset.data && !valid ? 'Catalog and index revisions differ. Refresh the published dataset.' : undefined)} retry={asset.retry} />
    {valid && <>
      {asset.data!.pricing_observation && <div className={`notice ${asset.data!.pricing_observation.older_than_documented_window_count ? 'warning' : ''}`} role="note" aria-label="Google source-time provenance"><Info size={17} /><span>Google latest-price as-of timestamps are source provenance, not tariff dates. Captured check: {exactDate(asset.data!.pricing_observation.observed_at)}. {asset.data!.pricing_observation.older_than_documented_window_count > 0 && <>{asset.data!.pricing_observation.older_than_documented_window_count.toLocaleString('en-US')} SKU timestamps are older than the API's advertised 12-hour age. Exact timestamps are retained; this is not a new tariff or a freshness guarantee.</>}</span></div>}
      <section className="panel source-notes"><h2>Source scope & billing notes</h2><details><summary>{asset.data!.billing_notes.length} source notes · view conditions and limitations</summary><ul tabIndex={0} aria-label="Scrollable source billing notes">{asset.data!.billing_notes.map((note, i) => <li key={i}>{note}</li>)}</ul></details>
        {provider.id === 'ovhcloud' && <p className="catalog-caution">Currency is not stated in the selected catalog. Amounts remain native; no USD or EUR is assumed.</p>}
        {provider.id === 'snowflake' && <p className="catalog-caution">PDF page text is source evidence. Table alignment and model-to-rate mappings are not reviewed.</p>}
        {asset.data!.source_evidence.map((evidence) => <details key={evidence.source_url}><summary>Exact response-byte evidence: {new URL(evidence.source_url).pathname.split('/').pop()}</summary><code>SHA-256: {evidence.response_sha256}</code></details>)}
        <details><summary>Catalog provenance</summary><dl className="record-facts"><dt>First observed</dt><dd>{exactDate(provider.first_seen_at)}</dd><dt>Catalog SHA-256</dt><dd><code>{provider.catalog_sha256}</code></dd><dt>Selected response SHA-256</dt><dd><code>{provider.source_sha256}</code></dd></dl></details>
      </section>
      <AssetNotice loading={index.loading} error={index.error ?? (records && !indexValid ? 'Incomplete or mismatched provider search index.' : undefined)} retry={index.retry} />
      {recordId && selected && <><AssetNotice loading={detail.loading} error={detail.error ?? (detail.data && !record ? 'Selected evidence differs from its index.' : undefined)} retry={detail.retry} />{record && <RecordDetail record={record} provider={provider} onClose={() => onProvider(provider.id)} onModel={onModel} data={data} />}</>}
      {recordId && indexValid && !selected && <div className="notice warning" role="status"><Info size={17} /><span>This record is not in the current selected source. Retained history is available on request; absence does not prove discontinuation.</span><button onClick={() => onProvider(provider.id)}>Clear selection</button></div>}
      {indexValid && <section className="panel native-catalog"><div className="section-heading"><div><h2>Native catalog</h2><p>Search all indexed identities, scope labels, units and currencies. Open a record for complete billing expressions.</p></div><button className="button" disabled={exporting} onClick={() => void exportRecords()}><Download size={15} />{exporting ? 'Loading complete export…' : 'Export filtered records'}</button></div>
        {exportError && <div className="notice warning" role="alert"><Info size={17} /><span>{exportError} No partial export was produced.</span><button onClick={() => void exportRecords()}>Retry export</button></div>}
        <div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search native catalog" placeholder="Model, route, SKU, region, unit, or currency…" value={search} onChange={(e) => update(setSearch, e.target.value)} /></label>
          <select aria-label="Filter catalog by record type" value={kind} onChange={(e) => update(setKind, e.target.value)}><option value="all">All record types</option>{Object.keys(provider.kind_counts).map((k) => <option value={k} key={k}>{kindLabel(k)}</option>)}</select>
          <select aria-label="Filter catalog by billing basis" value={basis} onChange={(e) => update(setBasis, e.target.value)}><option value="all">All billing bases</option>{billingBases.map((b) => <option key={b}>{b}</option>)}</select>
          <select aria-label="Filter catalog by pricing state" value={priceState} onChange={(e) => update(setPriceState, e.target.value)}><option value="all">All pricing states</option>{[...new Set(records.map((r) => r.pricing_state))].sort().map((s) => <option key={s}>{s}</option>)}</select>
        </div>
        <div className="table-scroll"><table className="native-table"><thead><tr><th>Source listing</th><th>Kind / access</th><th>Native pricing</th><th>Review</th><th>Details</th></tr></thead><tbody>{filtered.slice((pageNumber - 1) * 25, pageNumber * 25).map((r) => <tr key={r.id}>
          <td><strong>{r.label}</strong><code>{r.native_id}</code><small>{r.scope_label || 'No additional source scope published'}</small></td><td>{kindLabel(r.kind)}<small>{provider.access}</small><small>{r.billing_basis}</small></td>
          <td><span className="subtle-badge">{r.pricing_state}</span>{r.rate_preview.map((rate, i) => <small className="native-rate" key={i}>{rate.dimension}: {nativeRateText(rate)}</small>)}{!r.rate_count && <small>See source-native billing expressions</small>}{r.rate_count > 2 && <small>+ {r.rate_count - 2} more dimensions</small>}</td>
          <td><span className="subtle-badge">Not compared</span>{r.reviewed_model_ids.length > 0 && <small>Reviewed model identity linked</small>}</td><td><button className="text-link" aria-label={`View source record ${r.native_id}`} onClick={() => onProvider(provider.id, r.id)}>View <ArrowRight size={14} /></button></td>
        </tr>)}</tbody></table></div>
        {!filtered.length && <div className="empty-state"><h3>No matching source records</h3><p>Try another search, record type, or billing basis.</p></div>}<Pager page={pageNumber} total={filtered.length} onPage={setPage} />
      </section>}
      <section className="panel provider-history"><div className="section-heading"><div><h2>Observed source history</h2><p>{recordId ? 'Find retained events for this record on request.' : 'Observation batches first; individual event pages load on demand.'} No historical backfill.</p></div><button className="button" aria-expanded={historyOpen} onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? 'Hide source history' : 'Load source history'}</button></div>
        {historyOpen && <><AssetNotice loading={history.loading} error={history.error} retry={history.retry} />{history.data && <SourceHistory manifest={history.data} version={version} recordId={recordId} providerOnly onProvider={onProvider} />}</>}
      </section>
    </>}
  </>;
}

function RecordDetail({ record, provider, data, onClose, onModel }: { record: NativeRecord; provider: CatalogProvider; data: Dataset; onClose: () => void; onModel: (id: string) => void }) {
  const type = ['sku', 'sku_dimension', 'meter'].includes(record.kind) ? 'Cloud billing dimension' : record.kind === 'document_page' || record.kind === 'document_row' ? 'Source document evidence' : 'API model / route evidence';
  return <section className="panel record-detail" aria-label="Selected source record"><div className="section-heading"><div><div className="eyebrow">{type.toUpperCase()}</div><h2>{record.label}</h2><code>{record.native_id}</code></div><button className="button" onClick={onClose}>Close record</button></div>
    <div className="record-detail-body"><div className="catalog-source-summary"><span className="subtle-badge">{kindLabel(record.kind)}</span><span className="subtle-badge">{pricingState(record)}</span><span className="subtle-badge">Unreviewed billing · not compared</span></div>
      <p>{record.reviewed_model_ids.length ? 'The exact provider identity is linked to existing reviewed offers. These native rates are still unreviewed and do not replace calculator quotes.' : 'This source identity has not been linked to a reviewed canonical model. Similar names are not proof of equivalence.'}</p>
      <div className="catalog-source-links">{record.reviewed_model_ids.map((id) => <button className="text-link" key={id} onClick={() => onModel(id)}>Reviewed comparison: {data.models.find((m) => m.id === id)?.name ?? id} <ArrowRight size={14} /></button>)}<a className="text-link" href={record.source_url} target="_blank" rel="noopener noreferrer">Official record source <ArrowUpRight size={14} /></a></div>
      <dl className="record-facts"><dt>Source scope</dt><dd>{scopeLabel(record) || 'No additional scope published'}</dd><dt>Native units</dt><dd>{[...new Set(record.rates.map((r) => r.unit ?? 'Unit unverified'))].join(' · ') || 'See source expressions'}</dd><dt>Currencies</dt><dd>{[...new Set(record.rates.map((r) => r.currency ?? 'Currency unknown'))].join(' · ') || 'Not established by structured rates'}</dd></dl>
      {record.rates.length > 0 && <div className="table-scroll"><table><thead><tr><th>Dimension</th><th>Native amount / unit</th><th>Conditions</th></tr></thead><tbody>{record.rates.map((rate, i) => <tr key={i}><td>{rate.dimension}</td><td>{nativeRateText(rate)}</td><td><pre>{Object.keys(rate.conditions).length ? jsonText(rate.conditions) : 'No additional conditions captured'}</pre></td></tr>)}</tbody></table></div>}
      {record.billing.alignment_verified === false && <div className="notice warning"><Info size={16} /><span>Column alignment is unverified. Cells retain source order; do not infer a model-to-price mapping.</span></div>}
      {record.kind === 'document_page' && <div className="notice warning"><Info size={16} /><span>Extracted PDF text, not a parsed model-price table.</span></div>}
      <details><summary>Original billing expressions</summary>{Array.isArray(record.billing.cells) && <div className="source-cell-list">{record.billing.cells.map((cell, i) => <div key={i}><strong>{record.billing.alignment_verified === true && Array.isArray(record.billing.columns) ? record.billing.columns[i] : `Source cell ${i + 1}`}</strong><span>{jsonText(cell)}</span></div>)}</div>}<pre className="source-json" tabIndex={0} aria-label="Scrollable original billing expressions">{typeof record.billing.text === 'string' ? record.billing.text : jsonText(record.billing)}</pre></details>
      <details><summary>Region, route, tier, bands & source scope</summary><pre className="source-json" tabIndex={0} aria-label="Scrollable source scope">{jsonText(record.scope)}</pre></details>
      <details><summary>Published model / SKU metadata</summary><pre className="source-json" tabIndex={0} aria-label="Scrollable source metadata">{jsonText(record.metadata)}</pre></details>
      <small>Catalog revision {provider.revision}. Check freshness at the provider level; this is not a live billing guarantee.</small>
    </div>
  </section>;
}
