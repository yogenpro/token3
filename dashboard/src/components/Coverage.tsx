import { ArrowRight, Info } from 'lucide-react';
import type { CatalogIndex } from '../lib/catalog';
import { kindLabel, sourceFreshness } from '../lib/catalog';
import type { Dataset } from '../lib/data';
import { dateLabel, exactDate } from '../lib/pricing';

export function Coverage({ data, catalog, onModels, onProviders, onChanges }: {
  data: Dataset; catalog: CatalogIndex; onModels: (directory: string) => void; onProviders: (id: string) => void; onChanges: () => void;
}) {
  const c = catalog.coverage;
  const health = catalog.providers.map((p) => sourceFreshness(data.status.providers.find((s) => s.id === p.id)));
  const needsAttention = health.filter((h) => h.warning).length;
  const active = data.offerings.filter((o) => o.active);
  const reviewedConsistent = c.reviewed_model_count === data.models.length && c.reviewed_offering_count === data.offerings.length &&
    c.active_reviewed_offering_count === active.length;
  return <>
    <div className="page-heading"><div className="eyebrow">WHAT WE KNOW · WHAT WE DON'T</div><h1>Coverage, <span>without the guesswork.</span></h1><p>Comparable quotes are a reviewed subset of a broader source catalog. Different denominators stay separate.</p></div>
    <p className="coverage-asof">Projected snapshot: <time dateTime={catalog.updated_at} title={exactDate(catalog.updated_at)}>{dateLabel(catalog.updated_at, true)}</time>. Each source's latest successful check is listed below.</p>
    {!reviewedConsistent && <div className="notice warning" role="alert"><Info size={17} /><span>Reviewed data and coverage were published at different revisions. Refresh before using counts together.</span></div>}
    <div className="coverage-grid">
      <section className="panel coverage-card"><span className="eyebrow">REVIEWED COMPARISONS</span><h2>{data.models.length} canonical models</h2><strong>{active.length} active offers</strong><p>{data.offerings.length} retained offers, including inactive history · {new Set(data.offerings.map((o) => o.provider)).size} billing providers.</p><button className="text-link" onClick={() => onModels('reviewed')}>Browse reviewed models <ArrowRight size={15} /></button></section>
      <section className="panel coverage-card"><span className="eyebrow">MODEL DISCOVERY</span><h2>{c.model_listing_count.toLocaleString('en-US')} source listings</h2><strong>Models, routes and flavors</strong><p>Provider-scoped identities, not deduplicated models. Cloud meters and document rows are not included in this count.</p><button className="text-link" onClick={() => onModels('collected')}>Explore collected listings <ArrowRight size={15} /></button></section>
      <section className="panel coverage-card"><span className="eyebrow">NATIVE BILLING EVIDENCE</span><h2>{catalog.record_count.toLocaleString('en-US')} source records</h2><strong>{catalog.providers.length} provider groups</strong><p>Original amounts, units, conditions and unknowns. Native records are never calculator-eligible.</p><button className="text-link" onClick={() => onProviders('')}>Inspect source catalogs <ArrowRight size={15} /></button></section>
    </div>
    <div className="coverage-facets">
      <section className="panel coverage-breakdown"><h2>What was collected</h2><dl>{Object.entries(c.kind_counts).map(([kind, count]) => <div key={kind}><dt>{kindLabel(kind)}</dt><dd>{count.toLocaleString('en-US')}</dd></div>)}</dl></section>
      <section className="panel coverage-breakdown"><h2>Native billing bases</h2><p>Display facets, not unit conversion or economic equivalence.</p><dl>{Object.entries(c.billing_basis_counts).map(([basis, count]) => <div key={basis}><dt>{basis}</dt><dd>{count.toLocaleString('en-US')}</dd></div>)}</dl></section>
      <section className="panel coverage-breakdown"><h2>Pricing certainty</h2><p>A published native rate is not a reviewed comparison quote.</p><dl>{Object.entries(c.pricing_state_counts).map(([state, count]) => <div key={state}><dt>{state}</dt><dd>{count.toLocaleString('en-US')}</dd></div>)}</dl></section>
    </div>
    <section className="panel coverage-limits"><h2>Comparison depth and known gaps</h2><ul>
      <li><strong>{c.single_provider_model_count} models</strong> have only one active billing provider. Multiple tiers and prompt bands are not additional providers.</li>
      <li><strong>{c.gateway_only_model_count} models</strong> currently have gateway-only reviewed quotes. No upstream endpoint or direct-creator price is inferred.</li>
      <li><strong>{c.unknown_context_offering_count} active offers</strong> have unpublished context limits. Price review does not establish workload fit or account access.</li>
      <li><strong>{c.reviewed_price_change_count} verified reviewed price-change events</strong> are retained. First observations are not cuts or increases.</li>
    </ul><button className="text-link" onClick={onChanges}>Explore distinct change feeds <ArrowRight size={15} /></button></section>
    <section className="panel coverage-sources"><div className="section-heading"><div><h2>Source scope and check status</h2><p>{needsAttention} sources need attention or have limited/unverified checks. Health, freshness and review status are independent.</p></div></div><div className="table-scroll"><table><thead><tr><th>Selected source</th><th>Access</th><th>Collection status</th><th>Last successful check</th><th>Active reviewed offers</th></tr></thead><tbody>{catalog.providers.map((p) => {
      const status = data.status.providers.find((s) => s.id === p.id), freshness = sourceFreshness(status);
      return <tr key={p.id}><td><button className="text-link" onClick={() => onProviders(p.id)}>{p.name} <ArrowRight size={14} /></button><small>{p.source_kind} · {p.record_count.toLocaleString('en-US')} source records</small></td><td>{p.access}</td><td><span className={`health-badge ${freshness.warning ? 'warning' : ''}`}>{freshness.label}</span></td><td>{status?.last_success_at ? <time dateTime={status.last_success_at} title={exactDate(status.last_success_at)}>{dateLabel(status.last_success_at, true)}</time> : 'Unknown'}</td><td>{active.filter((o) => o.provider === p.id).length}</td></tr>;
    })}</tbody></table></div></section>
    <div className="notice"><Info size={17} /><span>Selected public source scopes are not universal market coverage. Unknown prices are not free. No launch dates, supplier routes, foreign-exchange conversions or historical backfills are inferred.</span></div>
  </>;
}
