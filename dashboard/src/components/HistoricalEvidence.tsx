import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, ArrowUpRight, Download, Info, Search } from 'lucide-react';
import { jsonText } from '../lib/catalog';
import { checkRows, evidenceKind, evidenceRows, historicalCheckChunkSchema, historicalEvidenceChunkSchema, historicalIndexChunkSchema, historicalIndexSchema,
  historicalManifestSchema, historicalSearch, matchingEvidence, summaryRows, validateHistoricalIndex, type HistoricalIndex, type HistoricalManifest, type HistoricalSummary } from '../lib/historical';
import { loadCatalogRows, useCatalogChunks } from '../lib/catalogChunks';
import { useCatalogAsset } from '../lib/useCatalogAsset';
import { downloadFile, exactDate } from '../lib/pricing';
import { AssetNotice, Pager } from './CatalogUI';
import { ProviderMark } from './UI';

const date = (value: string | null) => value ? new Date(value).toISOString().slice(0, 10) : 'Unknown';
const states = (values: Record<string, number>) => Object.entries(values).map(([k, n]) => `${n.toLocaleString('en-US')} ${k.replaceAll('_', ' ')}`).join(' · ');
const facts = 'Archive dates show source captures, not price-effective dates or model launches. Gaps do not prove retirement or tariff continuity.';

export function HistoricalEvidence({ providerId, recordId, onProvider, version }: { providerId: string; recordId: string; onProvider: (id: string, record?: string) => void; version: string }) {
  const index = useCatalogAsset('catalog/historical/index.json', historicalIndexSchema, version);
  const [search, setSearch] = useState('');
  const provider = index.data?.providers.find((p) => p.id === providerId);
  return <><div className="page-heading"><div className="eyebrow">RECOVERED PUBLIC SOURCES</div><h1>Historical <span>evidence.</span></h1><p>Explore past model identifiers, billing dimensions and published documents in their original terms.</p></div>
    <div className="notice" role="note"><Info size={18} /><span>Unreviewed historical evidence · excluded from comparisons. {facts}</span></div>
    <AssetNotice loading={index.loading} error={index.error} retry={index.retry} />
    {index.data && <>{providerId ? provider ? <HistoricalProvider key={providerId} index={index.data} providerId={providerId} recordId={recordId} onProvider={onProvider} /> : <div className="empty-state"><h2>Historical provider not found</h2><button className="button" onClick={() => onProvider('')}>All historical providers</button></div> : <>
      <div className="catalog-stats"><div><strong>{index.data.providers.length}</strong><span>provider groups with selected evidence</span></div><div><strong>{index.data.capture_count.toLocaleString('en-US')}</strong><span>retained source captures</span></div><div><strong>{index.data.assertion_count.toLocaleString('en-US')}</strong><span>assertions, not unique models or price changes</span></div></div>
      <p className="historical-intro">Coverage is partial. {index.data.check_count.toLocaleString('en-US')} retained lookup checks document failed, deferred or rejected lookups; later recovery does not erase earlier checks. Historical-only identifiers are included independently of today’s reviewed models.</p>
      <div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search historical providers" placeholder="Find a provider…" value={search} onChange={(e) => setSearch(e.target.value)} /></label></div>
      <div className="provider-grid">{index.data.providers.filter((p) => `${p.id} ${p.name}`.toLowerCase().includes(search.trim().toLowerCase())).map((p) => <section className="panel provider-card" key={p.id}><div className="provider-card-heading"><ProviderMark provider={p.id} /><h2>{p.name}</h2></div><div className="provider-card-counts"><strong>{p.capture_count} captures · {p.assertion_count.toLocaleString('en-US')} assertions</strong><span>{p.archive_from ? `Archive captures: ${date(p.archive_from)} to ${date(p.archive_to)}` : 'Official version evidence; no archive date inferred'}</span></div><p>{p.check_count ? `${p.check_count.toLocaleString('en-US')} retained unresolved lookup checks` : 'No unresolved checks in the selected batch; full provider history is not implied.'}</p><div className="provider-card-footer"><span>Partial source coverage</span><button className="text-link" aria-label={`Historical evidence for ${p.name}`} onClick={() => onProvider(p.id)}>Explore <ArrowRight size={14} /></button></div></section>)}</div>
    </>}</>}
  </>;
}

function HistoricalProvider({ index, providerId, recordId, onProvider }: { index: HistoricalIndex; providerId: string; recordId: string; onProvider: (id: string, record?: string) => void }) {
  const provider = index.providers.find((p) => p.id === providerId)!;
  const asset = useCatalogAsset(provider.detail_path, historicalManifestSchema, index.snapshot_sha256);
  const manifest = asset.data;
  const valid = !!manifest && manifest.provider === providerId && manifest.snapshot_sha256 === index.snapshot_sha256 && manifest.captures.length === provider.capture_count && manifest.assertion_count === provider.assertion_count && manifest.check_count === provider.check_count;
  return <><button className="text-link catalog-back" onClick={() => onProvider('')}><ArrowLeft size={15} /> All historical providers</button><div className="section-heading"><div><h2>{provider.name}</h2><p>{provider.capture_count} captures · {provider.assertion_count.toLocaleString('en-US')} assertions · partial history</p></div></div>
    {providerId === 'together' && <p className="historical-intro">Free documents only. Current Together comparisons remain paused.</p>}
    <div className="notice" role="note"><Info size={17} /><span>{states(provider.states)}. {provider.check_count ? `Lookup checks: ${states(provider.check_states)}.` : 'No unresolved checks in the selected batch.'} These are evidence states, not current collector health.</span></div>
    <AssetNotice loading={asset.loading} error={asset.error ?? (manifest && !valid ? 'Historical summary and provider manifest differ. Refresh the published dataset.' : undefined)} retry={asset.retry} />
    {valid && <HistoricalRecords key={index.snapshot_sha256} manifest={manifest} recordId={recordId} onProvider={onProvider} />}
  </>;
}

function HistoricalRecords({ manifest, recordId, onProvider }: { manifest: HistoricalManifest; recordId: string; onProvider: (id: string, record?: string) => void }) {
  const version = manifest.snapshot_sha256;
  const index = useCatalogChunks(manifest.index_chunks, historicalIndexChunkSchema, summaryRows, version);
  const indexValid = !!index.data && validateHistoricalIndex(index.data, manifest);
  const [search, setSearch] = useState(''), [kind, setKind] = useState('all'), [captureId, setCaptureId] = useState('all');
  const [dateBasis, setDateBasis] = useState('archive'), [from, setFrom] = useState(''), [to, setTo] = useState('');
  const [page, setPage] = useState(1), [checksOpen, setChecksOpen] = useState(false), [checkPage, setCheckPage] = useState(1);
  const [exporting, setExporting] = useState(false), [exportError, setExportError] = useState('');
  const exportRequest = useRef<AbortController | null>(null);
  const [exportProgress, setExportProgress] = useState('');
  useEffect(() => () => exportRequest.current?.abort(), []);
  const checks = useCatalogChunks(checksOpen ? manifest.check_chunks : undefined, historicalCheckChunkSchema, checkRows, version);
  const checksValid = !!checks.data && checks.data.length === manifest.check_count && checks.data.every((c) => c.provider === manifest.provider);
  const captures = useMemo(() => new Map(manifest.captures.map((c) => [c.id, c])), [manifest]);
  const selected = indexValid ? index.data!.find((r) => r.id === recordId) : undefined;
  const ref = selected && manifest.evidence_chunks.find((c) => c.path === selected.detail_path);
  const detail = useCatalogChunks(ref ? [ref] : undefined, historicalEvidenceChunkSchema, evidenceRows, version);
  const record = detail.data?.find((r) => r.id === selected?.id);
  const recordValid = !!selected && !!record && matchingEvidence(record, selected);
  const capture = recordValid ? captures.get(record.capture_id) : undefined;
  const selectedDate = (r: HistoricalSummary) => dateBasis === 'effective' ? r.source_reported_effective_at : dateBasis === 'publication' ? captures.get(r.capture_id)!.source_published_at : dateBasis === 'retrieval' ? captures.get(r.capture_id)!.retrieved_at : captures.get(r.capture_id)!.archive_capture_at;
  const filtered = indexValid ? index.data!.filter((r) => {
    const value = selectedDate(r)?.slice(0, 10);
    return (kind === 'all' || r.assertion_type === kind) && (captureId === 'all' || r.capture_id === captureId) && historicalSearch(r).includes(search.trim().toLowerCase()) &&
      (!from || !!value && value >= from) && (!to || !!value && value <= to);
  }) : [];
  const pageNumber = Math.min(page, Math.max(1, Math.ceil(filtered.length / 25)));
  const change = (set: (v: string) => void, value: string) => { set(value); setPage(1); };
  const exportRecords = async () => {
    const controller = new AbortController();
    exportRequest.current = controller;
    setExporting(true); setExportError('');
    try {
      const paths = new Set(filtered.map((r) => r.detail_path));
      const records = await loadCatalogRows(manifest.evidence_chunks.filter((r) => paths.has(r.path)), historicalEvidenceChunkSchema, evidenceRows,
        controller.signal, (done, total) => setExportProgress(`${done} of ${total} evidence chunks verified`));
      controller.signal.throwIfAborted();
      const values = new Map(records.map((r) => [r.id, r]));
      const complete = filtered.map((summary) => {
        const value = values.get(summary.id);
        if (!value || !matchingEvidence(value, summary)) throw new Error('Historical evidence differs from the search index.');
        return value;
      });
      const captureIds = new Set(complete.map((r) => r.capture_id));
      const assertionIds = new Set(complete.map((r) => r.id));
      downloadFile(JSON.stringify({ schema_version: 1, snapshot_sha256: version, provider: manifest.provider, comparison_eligible: false,
        captures: manifest.captures.filter((c) => captureIds.has(c.id)), assertions: complete,
        corrections: manifest.corrections.filter((c) => assertionIds.has(c.assertion_id) || assertionIds.has(c.supersedes)) }, null, 2), `${manifest.provider}-historical-evidence.json`, 'application/json');
    } catch (error) { if (!controller.signal.aborted) setExportError(error instanceof Error ? error.message : 'Historical export failed.'); }
    finally { setExporting(false); }
  };
  return <><AssetNotice loading={index.loading} error={index.error ?? (index.data && !indexValid ? 'Historical search index is incomplete or mismatched.' : undefined)} retry={index.retry} />
    <section className="panel historical-captures"><div className="section-heading"><div><h2>Retained captures</h2><p>Indexes and unparsed documents remain visible even when they yield no assertions.</p></div></div><details><summary>Inspect {manifest.captures.length} source captures and interpretation states</summary><div className="table-scroll"><table><thead><tr><th>Source</th><th>Archive capture</th><th>Source publication</th><th>Retrieved</th><th>Interpretation</th></tr></thead><tbody>{manifest.captures.map((c) => <tr key={c.id}><td><a className="text-link" href={c.replay_url ?? c.source_url} target="_blank" rel="noopener noreferrer">{c.source_kind.replaceAll('_', ' ')} <ArrowUpRight size={12} /></a><small>{c.assertion_count.toLocaleString('en-US')} assertions</small></td><td title={c.archive_capture_at ?? undefined}>{date(c.archive_capture_at)}</td><td title={c.source_published_at ?? undefined}>{date(c.source_published_at)}</td><td title={c.retrieved_at}>{date(c.retrieved_at)}</td><td>{c.state.replaceAll('_', ' ')}{c.returned_entries !== null && <small>{c.returned_entries} index entries; not recovered prices</small>}{c.cap_reached && <small>Index cap reached; completeness unknown</small>}</td></tr>)}</tbody></table></div></details></section>
    {recordId && selected && <><AssetNotice loading={detail.loading} error={detail.error ?? (detail.data && !recordValid ? 'Selected historical evidence differs from its index.' : undefined)} retry={detail.retry} />{recordValid && capture && <section className="panel record-detail historical-detail" aria-label="Selected historical evidence"><div className="section-heading"><div><div className="eyebrow">{evidenceKind(record.assertion_type).toUpperCase()}</div><h2>{record.label}</h2><code>{record.native_id}</code></div><button className="button" onClick={() => onProvider(manifest.provider)}>Close evidence</button></div><div className="record-detail-body"><span className="subtle-badge">Unreviewed historical · not compared</span><p>{facts} Source expressions retain their own units, currencies, regions and conditions; missing amounts are unknown.</p>
      <dl className="record-facts"><dt>Archive capture</dt><dd>{capture.archive_capture_at ? exactDate(capture.archive_capture_at) : 'Unknown / not archived'}</dd><dt>Source publication</dt><dd>{capture.source_published_at ? exactDate(capture.source_published_at) : 'Unknown'}</dd><dt>Retrieved</dt><dd>{exactDate(capture.retrieved_at)}</dd><dt>Reported effective</dt><dd>{record.source_reported_effective_at ? exactDate(record.source_reported_effective_at) : 'Unknown; not inferred from archive or prose dates'}</dd><dt>Interpretation</dt><dd>{capture.state.replaceAll('_', ' ')}</dd></dl>
      {record.assertion_type === 'historical_pdf_page' && <p>Unaligned PDF page text. Model-to-rate alignment and credit-to-currency mappings are unverified.</p>}
      {record.evidence.alignment_verified === false && <p>Column alignment is unverified. Cells retain source order.</p>}
      <div className="catalog-source-links"><a className="text-link" href={capture.source_url} target="_blank" rel="noopener noreferrer">Original source <ArrowUpRight size={13} /></a>{capture.replay_url && <a className="text-link" href={capture.replay_url} target="_blank" rel="noopener noreferrer">Archived capture <ArrowUpRight size={13} /></a>}</div>
      <details open><summary>Published historical expressions</summary><pre className="source-json" tabIndex={0} aria-label="Historical source expressions">{typeof record.evidence.text === 'string' ? record.evidence.text : jsonText(record.evidence)}</pre></details>
      <details><summary>Scope and provenance</summary><pre className="source-json" tabIndex={0} aria-label="Historical scope and provenance">{jsonText({ assertion_id: record.id, capture_id: capture.id, source_sha256: capture.source_sha256, identity_scope: record.identity_scope, request_scope: capture.scope, source_pointer: record.source_pointer, extractor: record.extractor })}</pre></details>
      {manifest.corrections.filter((c) => c.assertion_id === record.id || c.supersedes === record.id).map((c) => <div className="notice" key={c.id}><Info size={16} /><span>Append-only correction: {c.reason} ({date(c.recorded_at)}). Original assertions remain retained. Replacement {c.assertion_id}; supersedes {c.supersedes}.</span></div>)}
    </div></section>}</>}
    {recordId && indexValid && !selected && <div className="notice warning" role="status"><span>This assertion is not in the selected historical snapshot.</span><button onClick={() => onProvider(manifest.provider)}>Clear selection</button></div>}
    {indexValid && <section className="panel historical-records"><div className="section-heading"><div><h2>Historical assertions</h2><p>Search all retained identifiers, labels and source scopes. Repeated captures are separate evidence, not automatic price-change events.</p></div><button className="button" disabled={exporting} onClick={() => void exportRecords()}><Download size={15} />{exporting ? 'Loading complete historical export…' : 'Export filtered historical evidence'}</button></div>
      {exporting && <div className="catalog-toolbar" role="status"><span>{exportProgress || 'Loading historical evidence…'}</span><button className="button" onClick={() => exportRequest.current?.abort()}>Cancel historical export</button></div>}
      {exportError && <div className="notice warning" role="alert"><span>{exportError} No partial export was produced.</span><button onClick={() => void exportRecords()}>Retry historical export</button></div>}
      <div className="catalog-toolbar"><label className="search-field"><Search size={16} /><input aria-label="Search historical assertions" placeholder="Model ID, SKU, label or scope…" value={search} onChange={(e) => change(setSearch, e.target.value)} /></label><select aria-label="Historical evidence type" value={kind} onChange={(e) => change(setKind, e.target.value)}><option value="all">All evidence types</option>{[...new Set(index.data!.map((r) => r.assertion_type))].map((k) => <option key={k} value={k}>{evidenceKind(k)}</option>)}</select><select aria-label="Historical capture" value={captureId} onChange={(e) => change(setCaptureId, e.target.value)}><option value="all">All captures</option>{manifest.captures.filter((c) => c.assertion_count).map((c, i) => <option key={c.id} value={c.id}>Capture {i + 1}: archive {date(c.archive_capture_at)} · published {date(c.source_published_at)}</option>)}</select></div>
      <div className="catalog-toolbar historical-dates"><label>Date basis<select aria-label="Date basis" value={dateBasis} onChange={(e) => change(setDateBasis, e.target.value)}><option value="archive">Archive capture</option><option value="publication">Source publication</option><option value="retrieval">Retrieved</option><option value="effective">Reported effective</option></select></label><label>From<input aria-label="From" type="date" value={from} onChange={(e) => change(setFrom, e.target.value)} /></label><label>Through<input aria-label="Through" type="date" value={to} onChange={(e) => change(setTo, e.target.value)} /></label><span>Unknown dates are excluded only when a date bound is set. Rows follow ledger order.</span></div>
      <div className="table-scroll"><table className="native-table"><thead><tr><th>Historical identity / evidence</th><th>Type</th><th>Archive / publication</th><th>Review</th><th>Details</th></tr></thead><tbody>{filtered.slice((pageNumber - 1) * 25, pageNumber * 25).map((r) => <tr key={r.id}><td><strong>{r.label}</strong><code>{r.native_id}</code></td><td>{evidenceKind(r.assertion_type)}</td><td><span>Archive: {date(captures.get(r.capture_id)!.archive_capture_at)}</span><small>Published: {date(captures.get(r.capture_id)!.source_published_at)}</small></td><td><span className="subtle-badge">Not compared</span></td><td><button className="text-link" aria-label={`View historical evidence ${r.native_id}`} onClick={() => onProvider(manifest.provider, r.id)}>View <ArrowRight size={14} /></button></td></tr>)}</tbody></table></div>
      {!filtered.length && <div className="empty-state"><h3>No matching historical assertions</h3><p>Try another identifier, capture, evidence type or date basis. No matches do not prove a model was unavailable.</p></div>}<Pager page={pageNumber} total={filtered.length} onPage={setPage} />
    </section>}
    <section className="panel historical-checks"><div className="section-heading"><div><h2>Lookup gaps</h2><p>{manifest.check_count.toLocaleString('en-US')} retained checks. Deferred means not attempted; transport failures with no HTTP response are not provider outages.</p></div><button className="button" aria-expanded={checksOpen} onClick={() => setChecksOpen(!checksOpen)}>{checksOpen ? 'Hide lookup checks' : 'Load lookup checks'}</button></div>{checksOpen && <><AssetNotice loading={checks.loading} error={checks.error ?? (checks.data && !checksValid ? 'Historical lookup checks differ from their manifest.' : undefined)} retry={checks.retry} />{checksValid && <><div className="table-scroll"><table><thead><tr><th>State</th><th>Checked / planned</th><th>Target archive date</th><th>Response</th></tr></thead><tbody>{checks.data!.slice((checkPage - 1) * 25, checkPage * 25).map((c) => <tr key={c.id}><td><a href={c.source_url} target="_blank" rel="noopener noreferrer">{c.state.replaceAll('_', ' ')}</a></td><td title={c.checked_at ?? (c.recorded_at ? `Report recorded ${c.recorded_at}; lookup date has day precision` : undefined)}>{c.checked_date ?? date(c.checked_at)}</td><td>{date(c.archive_capture_at)}</td><td>{c.http_status === null ? 'No HTTP response recorded' : `HTTP ${c.http_status}`}{c.state === 'budget_deferred' && <small>No request or capture claimed</small>}</td></tr>)}</tbody></table></div><Pager page={checkPage} total={checks.data!.length} onPage={setCheckPage} /></>}</>}</section>
  </>;
}
