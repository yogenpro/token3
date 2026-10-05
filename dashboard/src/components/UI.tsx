import { ArrowUpRight, Cpu, Layers } from 'lucide-react';
import type { Model } from '../lib/data';
import { providerColor, providerInfo } from '../lib/data';

export function ProviderMark({ provider }: { provider: string }) {
  const info = providerInfo(provider);
  return <span className={`provider-mark provider-${provider}`} style={{ color: providerColor(provider), background: `color-mix(in srgb, ${providerColor(provider)} 8%, transparent)` }} aria-hidden="true">{info.initials}</span>;
}
export function ModelMark({ model, small = false }: { model: Model; small?: boolean }) {
  return <span className={`model-mark ${small ? 'small' : ''} creator-${model.creator.toLowerCase()}`} aria-hidden="true"><Cpu size={small ? 16 : 23} strokeWidth={1.7} /></span>;
}
export function Brand() {
  return <div className="brand" title="TokenTokenToken — Token cubed"><span className="brand-mark" aria-hidden="true"><Layers size={25} strokeWidth={2} /></span><span><span className="brand-wordmark" aria-hidden="true">Token<sup>3</sup></span><small>TokenTokenToken</small></span></div>;
}
export function SourceLink({ url, label }: { url: string; label: string }) {
  return <a className="icon-button source-link" href={url} target="_blank" rel="noopener noreferrer" aria-label={label} title={label}><ArrowUpRight size={16} /></a>;
}
