import { ArrowRight, ArrowUpRight, Info } from 'lucide-react';
import type { NativeChange } from '../lib/catalog';
import { providerInfo } from '../lib/data';
import { dateLabel, exactDate } from '../lib/pricing';

export function AssetNotice({ loading, error, retry }: { loading: boolean; error?: string; retry: () => void }) {
  if (error) return <div className="notice warning" role="alert"><Info size={18} /><span>{error}</span><button onClick={retry}>Retry catalog</button></div>;
  if (loading) return <div className="catalog-loading" role="status">Loading collected catalog…</div>;
  return null;
}
export function Pager({ page, total, size = 25, onPage }: { page: number; total: number; size?: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return <div className="catalog-pagination"><span>{total ? `${(page - 1) * size + 1}–${Math.min(page * size, total)} of ${total.toLocaleString('en-US')}` : '0 results'}</span><div><button className="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous page</button><span>Page {page} of {pages}</span><button className="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next page</button></div></div>;
}
export function NativeEvent({ event, onRecord }: { event: NativeChange; onRecord: (provider: string, record?: string) => void }) {
  return <article className="change-item native-change"><div className="change-icon other"><Info size={17} /></div><div className="change-content"><div className="change-top"><strong>{providerInfo(event.provider).name}</strong><time dateTime={event.observed_at} title={exactDate(event.observed_at)}>{dateLabel(event.observed_at)}</time></div><p>{event.title}</p><div className="change-model">{event.label}</div><span className="subtle-badge">Native source · not a reviewed comparison</span>{event.details.map((detail, i) => <div className="native-change-detail" key={i}><strong>{detail.field}</strong><div><span>{detail.before ?? 'Not published'}</span><ArrowRight size={13} /><span>{detail.after ?? 'Not published'}</span></div></div>)}{event.title === 'No longer in selected source' && <p className="change-explanation">Source absence is not proof that the vendor discontinued the model or service.</p>}{event.title === 'First observed listing' && <p className="change-explanation">Our discovery date, not a model launch date.</p>}<div className="catalog-event-links"><a className="text-link" href={event.source_url} target="_blank" rel="noopener noreferrer">Official source <ArrowUpRight size={13} /></a><button className="text-link" onClick={() => onRecord(event.provider, event.record_id ?? undefined)}>Explore source record <ArrowRight size={13} /></button></div></div></article>;
}
