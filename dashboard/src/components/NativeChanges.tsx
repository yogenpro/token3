import { Info } from 'lucide-react';
import { historyManifestSchema, type CatalogIndex, type ChangeCategory } from '../lib/catalog';
import { useCatalogAsset } from '../lib/useCatalogAsset';
import { AssetNotice } from './CatalogUI';
import { SourceHistory } from './SourceHistory';

export function NativeChanges({ catalog, category, onProvider }: { catalog: CatalogIndex; category: ChangeCategory; onProvider: (provider: string, record?: string) => void }) {
  const asset = useCatalogAsset(`catalog/changes/${category}.json`, historyManifestSchema, catalog.updated_at);
  return <><div className="notice"><Info size={17} /><span>{category === 'price' ? 'Native amount changes use the same explicit currency, unit, conditions, and scope. They are not reviewed model comparisons. Gateway changes describe advertised catalog prices, not a guaranteed selected supplier.' : category === 'rule' ? 'Billing formulas, units, currencies, conditions, and guide revisions. First-captured guides are observations, not historical price changes. Legacy events remain retained, including earlier source-time rule observations.' : 'Real discoveries, source absences, reappearances, and metadata changes. Discovery dates are not launch dates; source absence does not prove discontinuation.'}</span></div>
    <AssetNotice loading={asset.loading} error={asset.error} retry={asset.retry} />
    {asset.data && <section className="panel changes-panel"><SourceHistory key={category} manifest={asset.data} version={catalog.updated_at} catalog={catalog} onProvider={onProvider} /></section>}
  </>;
}
