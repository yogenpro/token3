import { comparisonsPaused, type Change, type Dataset } from './data';
import { rankOfferings, type Workload } from './pricing';

// One observed quote update can have several component events. Do not count
// three changed rates as three separate provider decisions or announcements.
export function reviewedChangeGroups(changes: Change[]) {
  const groups = new Map<string, Change[]>();
  for (const c of changes) {
    if (c.kind !== 'price_changed') continue;
    const key = `${c.offering_id}:${c.observed_at}`;
    groups.set(key, [...(groups.get(key) ?? []), c]);
  }
  return [...groups.entries()].map(([id, changes]) => ({ id, changes, observed_at: changes[0].observed_at }))
    .sort((a, b) => b.observed_at.localeCompare(a.observed_at) || a.id.localeCompare(b.id));
}

export function workloadPriceMap(data: Dataset, workload: Workload, tier: string, region: string, search: string) {
  const needle = search.trim().toLowerCase();
  return data.models.filter((m) => `${m.id} ${m.name} ${m.family} ${m.creator}`.toLowerCase().includes(needle)).map((model) => {
    const rows = rankOfferings(data, model.id, workload, tier).filter((r) => r.cost.eligible && (region === 'all' || r.offering.region === region));
    const cells = new Map<string, typeof rows>();
    for (const row of rows) cells.set(row.offering.provider, [...(cells.get(row.offering.provider) ?? []), row]);
    const minimum = rows[0]?.cost.perRequest;
    return { model, cells, minimum };
  });
}

export function comparisonProviders(data: Dataset, modelIds?: Set<string>) {
  return [...new Set(data.offerings.filter((o) => o.active && !comparisonsPaused(o.provider) && (!modelIds || modelIds.has(o.model_id))).map((o) => o.provider))].sort();
}
