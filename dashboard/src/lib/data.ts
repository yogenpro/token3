import { z } from 'zod';

const url = z.url().refine((value) => /^https?:\/\//.test(value), 'Source must be an HTTP(S) URL');
const timestamp = z.iso.datetime();
const rate = z.number().finite().nonnegative();
const modelSchema = z.object({
  id: z.string(), creator: z.string(), name: z.string(), version: z.string(),
  family: z.string(), open_weight: z.boolean(), description: z.string(),
  lifecycle: z.enum(['current', 'legacy', 'preview']).optional(), documentation_url: url.optional(),
});
const offeringSchema = z.object({
  id: z.string(), model_id: z.string(), provider: z.string(), provider_model_id: z.string(),
  context_window: z.number().int().positive().nullable(), quantization: z.string().nullable(),
  service_tier: z.enum(['standard', 'priority', 'flex']), region: z.string(), variant: z.string(),
  source_url: url, active: z.boolean(), first_observed_at: timestamp, last_seen_at: timestamp,
  min_input_tokens: z.number().int().nonnegative().optional(), max_input_tokens: z.number().int().nonnegative().nullable().optional(),
  max_output_tokens: z.number().int().nonnegative().nullable().optional(), pricing_notes: z.string().optional(),
}).refine((o) => o.max_input_tokens == null || o.max_input_tokens >= (o.min_input_tokens ?? 0), 'Invalid input pricing band');
const priceSchema = z.object({
  offering_id: z.string(), observed_at: timestamp, input_per_million: rate, output_per_million: rate,
  cache_read_per_million: rate.nullable(), cache_write_per_million: rate.nullable(),
  currency: z.literal('USD'), source_url: url, source_sha256: z.string(),
});
const changeSchema = z.object({
  id: z.string(), kind: z.enum(['offering_added', 'offering_removed', 'offering_restored', 'offering_updated', 'price_changed']),
  offering_id: z.string(), model_id: z.string(), provider: z.string(), observed_at: timestamp,
  field: z.string().nullable(), old: z.union([z.string(), z.number(), z.boolean()]).nullable(),
  new: z.union([z.string(), z.number(), z.boolean()]).nullable(), change_pct: z.number().nullable(),
});
const providerSchema = z.object({
  id: z.string(), name: z.string(), state: z.enum(['ok', 'error']), last_attempt_at: timestamp,
  last_success_at: timestamp.nullable(), offering_count: z.number().int().nonnegative(),
  source_url: url, source_sha256: z.string().nullable(), authoritative_catalog: z.boolean(), error: z.string().nullable(),
});
const statusSchema = z.object({
  schema_version: z.literal(1), last_run_at: timestamp, first_observed_at: timestamp.nullable(),
  observation_count: z.number().int().nonnegative(), providers: z.array(providerSchema),
});
export const datasetSchema = z.object({
  models: z.array(modelSchema), offerings: z.array(offeringSchema), prices: z.array(priceSchema),
  history: z.array(priceSchema), changes: z.array(changeSchema), status: statusSchema,
}).superRefine((data, ctx) => {
  const models = new Set(data.models.map((m) => m.id));
  const offerings = new Set(data.offerings.map((o) => o.id));
  const prices = new Set(data.prices.map((p) => p.offering_id));
  if (models.size !== data.models.length || offerings.size !== data.offerings.length || prices.size !== data.prices.length) {
    ctx.addIssue({ code: 'custom', message: 'Duplicate catalog entries' });
  }
  if (data.offerings.some((o) => !models.has(o.model_id) || (o.active && !prices.has(o.id))) ||
      [...data.prices, ...data.history].some((p) => !offerings.has(p.offering_id)) ||
      data.changes.some((c) => !models.has(c.model_id) || !offerings.has(c.offering_id))) {
    ctx.addIssue({ code: 'custom', message: 'Broken catalog references' });
  }
  if (data.history.length !== data.status.observation_count) {
    ctx.addIssue({ code: 'custom', message: 'Observation count does not match history' });
  }
});

export type Model = z.infer<typeof modelSchema>;
export type Offering = z.infer<typeof offeringSchema>;
export type Price = z.infer<typeof priceSchema>;
export type Change = z.infer<typeof changeSchema>;
export type Dataset = z.infer<typeof datasetSchema>;
export type ProviderStatus = z.infer<typeof providerSchema>;

export async function loadDataset(): Promise<Dataset> {
  const files = ['models.json', 'offerings.json', 'latest_prices.json', 'price_history.json', 'changes.json', 'status.json'];
  const result = await Promise.all(files.map(async (file) => {
    const response = await fetch(`${import.meta.env.BASE_URL}${file}`, { cache: 'no-store', signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw new Error(`Unable to load ${file} (HTTP ${response.status}).`);
    return response.json();
  }));
  const [models, offerings, prices, history, changes, status] = result;
  return datasetSchema.parse({ models, offerings, prices, history, changes, status });
}

export const providers: Record<string, { name: string; color: string; initials: string }> = {
  deepinfra: { name: 'DeepInfra', color: '#7148c1', initials: 'di' },
  novita: { name: 'Novita', color: '#0b7768', initials: 'N' },
  together: { name: 'Together AI', color: '#2f64c4', initials: 't' },
  fireworks: { name: 'Fireworks', color: '#b3541e', initials: '✦' },
  groq: { name: 'Groq', color: '#b74641', initials: 'g' },
  openai: { name: 'OpenAI API', color: '#1f6f58', initials: 'O' },
  anthropic: { name: 'Anthropic API', color: '#a14e24', initials: 'A' },
  gemini: { name: 'Google Gemini API', color: '#1765c1', initials: 'G' },
  vertex: { name: 'Google Vertex AI', color: '#4a58b7', initials: 'V' },
  bedrock: { name: 'Amazon Bedrock', color: '#886012', initials: 'B' },
  azure: { name: 'Microsoft Foundry', color: '#006593', initials: 'Az' },
};
export function providerInfo(id: string) {
  return providers[id] ?? { name: id, color: '#6b7280', initials: id.slice(0, 2) };
}
export function providerColor(id: string) {
  return `var(--provider-color-${id}, ${providerInfo(id).color})`;
}
export function isStale(timestamp: string | null, now = Date.now()) {
  return !timestamp || now - new Date(timestamp).getTime() > 48 * 60 * 60 * 1000;
}
