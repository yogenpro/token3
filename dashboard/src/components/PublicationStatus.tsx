import type { Dataset } from '../lib/data';
import { isStale } from '../lib/data';
import { dateLabel, exactDate } from '../lib/pricing';

export function PublicationStatus({ data }: { data: Dataset }) {
  const p = data.publication;
  return <section className={`publication-status ${isStale(data.status.last_run_at) ? 'publication-stale' : ''}`} aria-label="Published snapshot freshness">
    <div className="pub-item"><span className="pub-dot" /><strong>Collected through</strong><time dateTime={data.status.last_run_at} title={exactDate(data.status.last_run_at)}>{dateLabel(data.status.last_run_at, true)}</time></div>
    <span className="pub-sep" aria-hidden="true">·</span>
    <div className="pub-item"><strong>{p?.mode === 'development' ? 'Development session' : 'Site built'}</strong>{p ? <time dateTime={p.built_at} title={exactDate(p.built_at)}>{dateLabel(p.built_at, true)}</time> : <span>Build time unavailable</span>}</div>
    {p?.commit_sha && <><span className="pub-sep" aria-hidden="true">·</span><div className="pub-item"><span>Snapshot</span><code>{p.commit_sha.slice(0, 7)}</code></div></>}
    <p>Published snapshot, not a live provider check. A new build does not make old quotes fresh.</p>
  </section>;
}
