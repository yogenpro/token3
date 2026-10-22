<!-- Public-source test excerpt, not production observations or a historical backfill.
Captured 2026-10-22 from https://developers.openai.com/api/docs/pricing.md.
Full source SHA-256: 129d6019819379a6f30edc0811d4631ddb085dcd4b3b1d0012a945cd1af1bfbf
The same SHA was retained by the failing 2026-10-21 collection. -->

Prices per 1M tokens.
Short context: ≤272K input tokens. Long context: >272K input tokens.

### Standard pricing data

| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6-astra | $10.00 | $50.00 | $1.00 | $12.50 | $25.00 | $20.00 | $75.00 | $2.00 | $25.00 | $50.00 |
| gpt-6.1-sol | $2.00 | $10.00 | $0.10 | $2.50 | $5.00 | $4.00 | $15.00 | $0.20 | $5.00 | $10.00 |
| gpt-6-luna | $0.10 | $0.50 | $0.01 | $0.125 | $0.25 | $0.20 | $0.75 | $0.02 | $0.25 | $0.50 |
| gpt-6-sol | $2.00 | $10.00 | $0.20 | $2.50 | $5.00 | $4.00 | $15.00 | $0.40 | $5.00 | $10.00 |
| gpt-5.6-sol | $4.00 | $20.00 | $0.40 | $5.00 | $10.00 | $8.00 | $30.00 | $0.80 | $10.00 | $20.00 |
| gpt-5.4 (<272K context length) | $2.50 | $15.00 | $0.25 | - | - | $5.00 | $22.50 | $0.50 | - | - |

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| gpt-5.4-mini | $0.75 | $4.50 | $0.075 |

### Batch pricing data

| Model | Short context input | Short context output | Short context cached input | Short context 30m write | Short context 12h write | Long context input | Long context output | Long context cached input | Long context 30m write | Long context 12h write |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-6-astra | $5.00 | $25.00 | $0.50 | $6.25 | $12.50 | $10.00 | $37.50 | $1.00 | $12.50 | $25.00 |
