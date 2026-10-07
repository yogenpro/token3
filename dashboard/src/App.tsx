import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, ExternalLink, Info, Moon, RefreshCw, Sun } from 'lucide-react';
import { isStale, loadDataset, type Dataset } from './lib/data';
import { dateLabel, defaultWorkload, downloadFile, normalizeWorkload, type Workload } from './lib/pricing';
import { Compare } from './components/Compare';
import { ChangesView } from './components/Changes';
import { Explorer } from './components/Explorer';
import { Methodology } from './components/Methodology';
import { Sidebar, type View } from './components/Sidebar';
import { Providers } from './components/Providers';
import { AssetNotice } from './components/CatalogUI';
import { catalogIndexSchema } from './lib/catalog';
import { useCatalogAsset } from './lib/useCatalogAsset';

function initialState() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const workload = { ...defaultWorkload };
  for (const [param, key] of [['input', 'inputTokens'], ['output', 'outputTokens'], ['cache', 'cacheHitPercent'], ['requests', 'requests']] as const) {
    if (params.has(param)) workload[key] = Number(params.get(param));
  }
  const tier = params.get('tier');
  return { view: (['compare', 'models', 'providers', 'changes', 'methodology'].includes(view ?? '') ? view : 'compare') as View, model: params.get('model') ?? 'openai/gpt-oss-120b', workload: normalizeWorkload(workload), tier: ['standard', 'priority', 'flex', 'all'].includes(tier ?? '') ? tier! : 'standard', provider: params.get('provider') ?? '', record: params.get('record') ?? '', directory: params.get('directory') === 'collected' ? 'collected' : 'reviewed', feed: ['price', 'rule', 'catalog'].includes(params.get('feed') ?? '') ? params.get('feed')! : 'reviewed' };
}
function initialTheme() {
  try {
    // Preserve an existing theme preference from before the rebrand.
    const saved = localStorage.getItem('tokentokentoken-theme') ?? localStorage.getItem('token-ledger-theme');
    return saved === 'dark' ? 'dark' : 'light';
  } catch { return 'light'; }
}

export function App() {
  const [initial] = useState(initialState);
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(true);
  const [toast, setToast] = useState('');
  const [view, setView] = useState<View>(initial.view);
  const [modelId, setModelId] = useState(initial.model);
  const [providerId, setProviderId] = useState(initial.provider);
  const [recordId, setRecordId] = useState(initial.record);
  const [directory, setDirectory] = useState(initial.directory);
  const [feed, setFeed] = useState(initial.feed);
  const [tier, setTier] = useState(initial.tier);
  const [workload, setWorkload] = useState<Workload>(initial.workload);
  const [theme, setTheme] = useState(initialTheme);
  const request = useRef(0);
  const [catalogRefresh, setCatalogRefresh] = useState(0);
  const catalog = useCatalogAsset(['models', 'providers', 'changes'].includes(view) ? 'catalog/index.json' : null, catalogIndexSchema, `${data?.status.last_run_at ?? ''}:${catalogRefresh}`);
  const refresh = useCallback(async (notify = false) => {
    const id = ++request.current;
    setRefreshing(true);
    try {
      const next = await loadDataset();
      if (id !== request.current) return;
      setData(next); setError('');
      setCatalogRefresh((n) => n + 1);
      setModelId((current) => next.models.some((m) => m.id === current) ? current : next.models[0]?.id ?? '');
      if (notify) setToast('Latest published dataset checked. Live collection runs separately.');
    } catch (err) {
      if (id !== request.current) return;
      console.error('Dataset loading failed', err);
      setError(err instanceof Error && err.name !== 'ZodError' ? err.message : 'The dataset is incomplete or invalid. Run the collectors and rebuild.');
    } finally { if (id === request.current) setRefreshing(false); }
  }, []);
  useEffect(() => { void refresh(); return () => { request.current++; }; }, [refresh]);
  useEffect(() => { if (!toast) return; const timeout = setTimeout(() => setToast(''), 4500); return () => clearTimeout(timeout); }, [toast]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('tokentokentoken-theme', theme); } catch { /* Storage can be unavailable in private browsing. */ }
  }, [theme]);
  useEffect(() => {
    const params = new URLSearchParams();
    params.set('model', modelId);
    if (view !== 'compare') params.set('view', view);
    if (view === 'providers' && providerId) { params.set('provider', providerId); if (recordId) params.set('record', recordId); }
    if (view === 'models' && directory !== 'reviewed') params.set('directory', directory);
    if (view === 'changes' && feed !== 'reviewed') params.set('feed', feed);
    if (tier !== 'standard') params.set('tier', tier);
    for (const [param, key] of [['input', 'inputTokens'], ['output', 'outputTokens'], ['cache', 'cacheHitPercent'], ['requests', 'requests']] as const) if (workload[key] !== defaultWorkload[key]) params.set(param, String(workload[key]));
    window.history.replaceState(null, '', `${window.location.pathname}?${params}${window.location.hash}`);
  }, [modelId, view, workload, tier, providerId, recordId, directory, feed]);
  const selectModel = (id: string) => { setModelId(id); setView('compare'); setTier('standard'); };
  const openProvider = (id: string, record = '') => { setProviderId(id); setRecordId(record); setView('providers'); };
  const model = data?.models.find((m) => m.id === modelId);
  const failed = data?.status.providers.filter((p) => p.state === 'error' || isStale(p.last_success_at)).length ?? 0;
  const latestObservedAt = data?.prices.reduce((latest, p) => p.observed_at > latest ? p.observed_at : latest, '') ?? '';
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to content</a><Sidebar models={data?.models ?? []} selected={modelId} view={view} onView={setView} onModel={selectModel} changeCount={data?.changes.filter((c) => c.kind === 'price_changed').length ?? 0} />
    <main id="main-content" className="main-content"><header className="topbar"><div className="breadcrumb">Dashboard <span>/</span> <strong>{view === 'compare' ? 'Compare prices' : view === 'models' ? 'Model explorer' : view === 'providers' ? 'Provider catalogs' : view === 'changes' ? 'Recent changes' : 'Methodology'}</strong></div><div className="topbar-actions"><span className={`update-status ${failed ? 'warning' : ''}`} title="Time of the newest published price observation, not a live billing guarantee"><span className="live-dot" />{data ? failed ? `${failed} collectors need attention` : `Observed ${latestObservedAt ? dateLabel(latestObservedAt, true) : '—'}` : 'Loading observations'}</span><button className={`icon-button ${refreshing ? 'spinning' : ''}`} disabled={refreshing} aria-label="Refresh published dataset" title="Refresh published dataset (does not run collectors)" onClick={() => void refresh(true)}><RefreshCw size={16} /></button><span className="topbar-divider" /><button className="icon-button" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button><button className="button export-button" aria-label="Export data" title="Export reviewed comparison data; native catalogs export from provider pages" disabled={!data} onClick={() => data && downloadFile(JSON.stringify(data, null, 2), 'tokentokentoken-dataset.json', 'application/json')}><Download size={15} /><span>Export reviewed</span></button></div></header>
      {error && <div className="error-notice" role="alert"><Info size={18} /><div><strong>Could not load fresh observations</strong><p>{error}{data && ' Showing the previously loaded dataset.'}</p></div><button className="button" onClick={() => void refresh()}>Retry</button></div>}
      {!data ? refreshing ? <div className="loading-state" role="status"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-subtitle" /><div className="skeleton skeleton-selector" /><div className="stat-grid">{[1, 2, 3, 4].map((n) => <div className="skeleton skeleton-card" key={n} />)}</div><div className="skeleton skeleton-table" /><span className="sr-only">Loading official pricing observations…</span></div> : <div className="empty-state"><Info size={32} /><h1>The dataset isn’t ready yet.</h1><p>Generate official observations locally with <code>python3 -m scripts.collect</code>, then refresh this page.</p><button className="button primary" onClick={() => void refresh()}>Try again</button></div> : <>
        {failed > 0 && <div className="notice warning"><Info size={17} /><span>Some collectors have failed or are more than 48 hours old. Last known prices are retained, not silently treated as fresh.</span><button onClick={() => setView('methodology')}>Check sources</button></div>}
        {view === 'compare' && model && <Compare data={data} model={model} onModel={selectModel} tier={tier} onTier={setTier} workload={workload} onWorkload={setWorkload} onChanges={() => setView('changes')} onMethodology={() => setView('methodology')} onProvider={openProvider} />}
        {['models', 'providers', 'changes'].includes(view) && <AssetNotice loading={catalog.loading} error={catalog.error} retry={catalog.retry} />}
        {view === 'models' && <Explorer data={data} onModel={selectModel} catalog={catalog.data} directory={directory} onDirectory={setDirectory} onProvider={openProvider} />}
        {view === 'providers' && catalog.data && <Providers data={data} catalog={catalog.data} providerId={providerId} recordId={recordId} onProvider={openProvider} onModel={selectModel} />}
        {view === 'changes' && <ChangesView data={data} catalog={catalog.data} feed={feed} onFeed={setFeed} onProvider={openProvider} />}
        {view === 'methodology' && <Methodology data={data} />}
      </>}
      <footer className="page-footer"><span>TokenTokenToken <span className="footer-dot">·</span> An independent inference price watch</span><button onClick={() => setView('methodology')}>Transparent by design <ExternalLink size={12} /></button></footer>
    </main>{toast && <div className="toast" role="status"><Info size={16} />{toast}</div>}
  </div>;
}
