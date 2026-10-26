import { useEffect, useMemo, useState } from 'react';
import { ChartNoAxesCombined, Info } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Dataset, Model, Price } from '../lib/data';
import { providerColor, providerInfo } from '../lib/data';
import { dateLabel, exactDate, historyRows, inputBandLabel, money as formatMoney, quoteUnit, unitLabel, type QuoteUnit } from '../lib/pricing';

type Metric = keyof Pick<Price, 'input_per_million' | 'output_per_million' | 'cache_read_per_million'>;
const metrics: [Metric, string][] = [['input_per_million', 'Input'], ['output_per_million', 'Output'], ['cache_read_per_million', 'Cache read']];
export function History({ data, model, tier, unit = 'USD', period = 'peak' }: { data: Dataset; model: Model; tier: string; unit?: QuoteUnit; period?: string }) {
  const money = (value: number) => formatMoney(value, false, unit);
  const [metric, setMetric] = useState<Metric>('input_per_million');
  const [days, setDays] = useState(30);
  const [hidden, setHidden] = useState<string[]>([]);
  useEffect(() => { setHidden([]); }, [model.id, tier, unit, period]);
  const offerings = useMemo(() => data.offerings.filter((o) => o.model_id === model.id && quoteUnit(o) === unit && (o.provider !== 'deepseek' || o.variant === period) && (tier === 'all' || o.service_tier === tier)), [data, model.id, tier, unit, period]);
  const rows = useMemo(() => historyRows(data.history, offerings, metric, days), [data.history, offerings, metric, days]);
  const providerIds = [...new Set(offerings.map((o) => o.provider))];
  const visible = offerings.filter((o) => !hidden.includes(o.provider));
  const hasValues = rows.some((row) => visible.some((o) => typeof row[o.id] === 'number'));
  const first = rows[0]?.timestamp ?? Date.now();
  const last = rows.at(-1)?.timestamp ?? first;
  const uniqueDays = new Set(rows.map((r) => new Date(r.timestamp!).toISOString().slice(0, 10))).size;
  const label = (id: string) => { const o = offerings.find((item) => item.id === id); return o ? `${providerInfo(o.provider).name}${o.variant !== 'standard' ? ` · ${o.variant}` : ''}${o.service_tier !== 'standard' ? ` · ${o.service_tier}` : ''}${o.region !== 'unspecified' ? ` · ${o.region}` : ''}${inputBandLabel(o) ? ` · ${inputBandLabel(o)}` : ''}` : id; };
  const snapshotValues = rows.flatMap((r) => visible.map((o) => r[o.id]).filter((v): v is number => typeof v === 'number'));
  const observationIds = new Set(offerings.map((o) => o.id));
  const observations = data.history.filter((p) => observationIds.has(p.offering_id) && (days === 0 || new Date(p.observed_at).getTime() >= Date.now() - days * 86400000));
  return <section className="panel history-panel"><div className="section-heading"><div><div className="eyebrow">THE LONG VIEW</div><h2>Price history <span className="heading-unit">{unitLabel(unit)} / 1M tokens</span></h2></div><select aria-label="History date range" className="compact-select" value={days} onChange={(e) => setDays(Number(e.target.value))}><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={0}>All time</option></select></div>
    <div className="history-controls"><div className="segments" role="group" aria-label="History price metric">{metrics.map(([key, name]) => <button key={key} onClick={() => setMetric(key)} className={metric === key ? 'active' : ''}>{name}</button>)}</div><span className="history-observations">{uniqueDays} {uniqueDays === 1 ? 'day' : 'days'} observed</span></div>
    {hasValues && uniqueDays < 2 ? <div className="first-observation" role="region" aria-label={`First observed price snapshot for ${model.name}`}><Info size={22} /><div><strong>First observed {dateLabel(new Date(first).toISOString())}</strong><p>One observed date, not a price trend. No earlier prices are backfilled.</p><span className="snapshot-price">{money(Math.min(...snapshotValues))}{Math.max(...snapshotValues) !== Math.min(...snapshotValues) ? ` – ${money(Math.max(...snapshotValues))}` : ''} <small>/ 1M tokens · {metrics.find(([key]) => key === metric)?.[1].toLowerCase()}</small></span><p>Tier, region and prompt-band differences remain in the exact observations below.</p></div></div> : hasValues ? <div className="chart-container" role="img" aria-label={`${metrics.find(([key]) => key === metric)?.[1]} price history for ${model.name}. ${uniqueDays} observed days. A table of exact observations is available below.`}><ResponsiveContainer width="100%" height={260}>
      <LineChart data={rows} margin={{ top: 20, right: 24, left: -8, bottom: 10 }} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--chart-grid)" />
        <XAxis dataKey="timestamp" type="number" domain={first === last ? [first - 43200000, last + 43200000] : [first, last]} ticks={rows.length < 6 ? rows.map((r) => r.timestamp!) : undefined} tickFormatter={(t: number) => dateLabel(new Date(t).toISOString())} tick={{ fontSize: 'var(--text-xs)', fill: 'var(--muted)' }} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis domain={[0, 'auto']} tickFormatter={(v: number) => money(v)} tick={{ fontSize: 'var(--text-xs)', fill: 'var(--muted)' }} axisLine={false} tickLine={false} width={70} />
        <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)', fontSize: 'var(--text-sm)', boxShadow: '0 8px 24px #16234512' }} labelFormatter={(timestamp) => exactDate(new Date(Number(timestamp)).toISOString())} formatter={(value, name) => [money(Number(value)), label(String(name))]} />
        {visible.map((o) => <Line key={o.id} dataKey={o.id} name={o.id} type="stepAfter" stroke={providerColor(o.provider)} strokeWidth={2.4} strokeDasharray={o.variant !== 'standard' || o.service_tier !== 'standard' ? '5 4' : undefined} dot={rows.length < 20 ? { r: 4, strokeWidth: 2, fill: 'var(--surface)' } : false} activeDot={{ r: 6 }} connectNulls={false} isAnimationActive={false} />)}
      </LineChart>
    </ResponsiveContainer></div> : <div className="chart-empty"><ChartNoAxesCombined size={30} /><strong>{visible.length === 0 ? 'All providers are hidden' : 'No published observations for this selection'}</strong><span>{visible.length === 0 ? 'Click a provider below to show its history.' : 'Try a different metric or a wider date range. Unknown cache prices are not plotted as zero.'}</span></div>}
    <div className="chart-legend" aria-label="Toggle providers in history">{providerIds.map((id) => <button key={id} aria-pressed={!hidden.includes(id)} onClick={() => setHidden(hidden.includes(id) ? hidden.filter((p) => p !== id) : [...hidden, id])} className={hidden.includes(id) ? 'hidden-series' : ''}><span style={{ background: providerColor(id) }} />{providerInfo(id).name}</button>)}</div>
    {uniqueDays < 2 && <div className="history-note"><Info size={14} /><span>{uniqueDays === 1 ? 'Day one of tracking. This snapshot contains real observations; a trend needs more days.' : 'No historical backfill. History grows with each successful daily collection.'}</span></div>}
    <details className="history-data"><summary>View exact observations <span>{observations.length}</span></summary><div className="table-scroll"><table><thead><tr><th>Offering</th><th>Observed at (UTC)</th><th>{metrics.find(([key]) => key === metric)?.[1]} / 1M</th><th>Source</th></tr></thead><tbody>{observations.map((p) => <tr key={`${p.offering_id}-${p.observed_at}`}><td>{label(p.offering_id)}</td><td>{exactDate(p.observed_at)}</td><td>{p[metric] === null ? 'Not published' : money(p[metric]!)}</td><td><a href={p.source_url} target="_blank" rel="noopener noreferrer">Official source</a></td></tr>)}</tbody></table></div></details>
  </section>;
}
