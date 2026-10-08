# Bounded daily-collection recovery

## Status and activation

Recovery is **off unless `ENABLE_SELF_HEALING=true`**. An OpenAI credential is not inferred from a local ChatGPT/Codex login, reused from a collector, or committed anywhere. Pages remains separately disabled.

To activate after reviewing these boundaries:

1. Create a dedicated OpenAI project/key that can use the selected models and the Responses API. Set appropriate organization/project rate limits and billing controls; monitor usage. **Budget alerts may be soft thresholds, not hard spend caps.** The workflow's one-attempt rule and agent timeouts bound activity, not a guaranteed dollar amount. Use provider-enforced limits where available; do not assume a monthly budget alert stops API calls.
2. Store the key as the repository Actions secret `OPENAI_API_KEY`, not an `.env` or `VITE_` variable. For example, run `gh secret set OPENAI_API_KEY --repo yogenpro/token3` and enter it privately at the prompt. Neither the dashboard nor the collector receives it.
3. Repository Settings → Actions → General → Workflow permissions must allow **GitHub Actions to create and approve pull requests**. Keep the default workflow permission **read-only**. The required setting permits PR creation; this implementation does **not** ask the PR-author bot to formally approve its own PR.
4. Configure models available to the dedicated project. Defaults follow this project's routing policy: repair `gpt-6-luna` (medium effort), independent high-risk review `gpt-6.1-sol` (high effort). `SELF_HEAL_REPAIR_MODEL` may be `gpt-6-luna` or `gpt-6.1-sol`; `SELF_HEAL_REVIEW_MODEL` must be `gpt-6.1-sol`. Missing model access stops recovery rather than silently choosing another provider/model. Broader repair-model escalation is an explicit operator choice, not automatic.
5. Enable `gh variable set ENABLE_SELF_HEALING --body true --repo yogenpro/token3`. Set it to `false` to stop new attempts immediately. Cancellation of an already running recovery is a separate action; disable/cancel it before changing policy or credentials.

No PAT or GitHub App secret is needed. Every GitHub write is a trusted controller operation with a job-scoped `GITHUB_TOKEN`, not an AI tool. Native repository auto-merge need not be enabled. Automatic merging is explicitly rejected if the default branch is protected or governed by a branch ruleset. GitHub indirect merges can mark a PR merged without satisfying that PR's approval requirements, so this controller must not use an existing push-bypass privilege as a substitute for compliance. Protected-branch integration requires a policy-aware GitHub App/merge-queue design or manual merging; no protection setting is disabled. If protection requires a formal approval by another GitHub identity, this same-bot setup is insufficient: use manual merging or a separately scoped GitHub App/reviewer identity.

## Sequence

1. `collect.yml` preserves last-good prices, commits valid provider updates/health, and uploads a small failed-attempt context for seven days. The context contains provider IDs, timestamps and already-redacted errors, not raw/authenticated responses.
2. `self-heal.yml` listens only for failed **scheduled**, default-branch `Collect official prices` runs. It verifies the actual GitHub run/workflow/repository, checks a seven-day window, and creates one bot-authored recovery issue assigned to the owner of a user-owned repository. Org owners should subscribe an appropriate maintainer to recovery issues.
3. Deduplication uses the trusted bot issue/PR marker for the original run. **One attempt per original failed run**, including reruns of that failure; there is no autonomous retry/edit/review loop. A manual dispatch accepts a failed scheduled run ID but does not override deduplication, source scope or safety policy.
4. A trusted preflight fetches the selected public source **without any collector or AI keys**. If the current trusted parser already succeeds and reviewed economics/scope are unchanged, it dispatches one replacement collection without inventing a repair PR. Otherwise it captures public evidence and an immutable reviewed baseline.
5. A read-only Codex repair advisor proposes structured JSON file contents. It cannot commit, push, create PRs, deploy, or access collector credentials. A separate trusted job validates the allowlist/AST/size limits and creates the recovery branch and PR.
6. The controller explicitly dispatches `ci.yml` on the exact recovery head. GitHub-token-created PR events may require a human to approve normal PR-triggered workflows, so they are **not relied upon**. Recovery CI has no collector/OpenAI secrets or write permissions. It checks the trusted evidence origin, replays the public source, verifies exact reviewed-price/scope/provenance equivalence, and proves the new regression fails against the original parser. Then it runs all existing unit, collector, typecheck, build and browser checks.
7. A second read-only Codex session independently reviews the proposed contents. It must approve without unresolved risks and bind its structured verdict to the exact head SHA and CI run. CI passing alone is insufficient. The reviewer does not execute proposed code or formally self-approve a bot-authored PR.
8. The merge controller re-reads the actual PR, branch refs, blobs, file modes and CI results. It rejects protected/ruleset-governed default branches, changed heads/bases, fork/foreign PRs, renamed/deleted/executable/symlink files, unexpected paths, changed proposal bytes or stale/invalid reviews. It publishes a separate independent-review commit status and PR comment.
9. The controller creates a normal two-parent merge using **exactly the tested tree** and updates the default branch with `force:false`. This is an atomic fast-forward guard: a concurrently advanced default branch cannot be silently included in an untested merge. GitHub must confirm the PR became merged before proceeding. No force-push, rebasing or branch-protection bypass is performed.
10. It explicitly dispatches one replacement `collect.yml` run, tagged with the original failure ID. The issue closes only if that complete strict collection succeeds. Replacement runs are `workflow_dispatch`, not schedules, so their failures **never invoke another AI recovery loop**; the issue stays open for manual intervention.

## Eligible repairs

Initial coverage is intentionally narrow: **one reviewed-provider public-source parser failure** for DeepInfra, Novita, Together, Fireworks, Groq, OpenAI, Anthropic, Gemini, Vertex, Bedrock or Azure. Authenticated catalog failures that cannot be reproduced from the selected public source do not qualify. Inventory-only/shared collectors, network outages, credential/billing/account problems, CI/infrastructure failures, multiple provider failures and actual price/scope changes create a manual-intervention issue instead.

Automatic changes are limited to:

- The selected `providers/<provider>.py` **`parse()` body** and new pure `_recovery_*` helpers. Existing helpers, classes, transport/collect methods, sources, imports, model mappings and other module-level behavior are immutable, apart from narrowly permitted non-shadowing pure stdlib imports.
- One **new** `tests/test_recovery_<failed-run-id>.py` regression module.
- Small **new** `tests/fixtures/recovery-<failed-run-id>-<slug>.{html,json,md,txt}` files.

At most six files, 128 KiB per file, and a 512 KiB proposal. Existing tests and fixtures cannot be rewritten. A proposed repair cannot edit workflows, recovery policy/prompts, dependencies, credentials, normalizers, catalog aliases, dashboard code, any warehouse/current-price/history files, raw archives or collection retention.

The replay must preserve every reviewed monetary amount, currency, source URL, identity, region, tier, variant, context/output limit, token-band boundary and pricing caveat. Missing/extra quotes or changed economics require a maintainer to verify and curate the source. This is specifically designed for representation changes like Vertex's four-to-six-column table update, **not** for automatically deciding new billing semantics.

## Security and residual risk

Vendor text, diagnostics, model output and code comments are untrusted data, not instructions. Prompts explicitly reject embedded instructions, but prompts are **not** the security boundary. Both AI sessions use read-only sandboxes, drop sudo, receive no GitHub write or collector secrets, and return JSON only. Their structured output is never `eval`ed, shell-expanded or used to select arbitrary commands. Privileged controller jobs check out trusted default-branch code, never the proposed head, and never execute the proposed Python.

Generated code runs only in secret-free CI before approval. Because it will later run in the credentialed collector, AST restrictions also reject environment/network/filesystem/reflection access and changes to protected transport/registry/completeness behavior. These are conservative sanity checks, **not a Python sandbox or a formal proof of parser safety/economic meaning**. The independent high-risk review, immutable existing tests, source replay, exact-tree merge and narrow scope are additional required controls. AI can still be wrong; maintainers should monitor issues/PRs and can disable the feature or require manual merges if that residual risk is unacceptable.

Actions and Codex CLI versions are pinned; upgrades to them, model routing, prompts or policy are manual reviewed changes. Evidence/proposals/reviews are temporary Actions artifacts with seven-day retention, not Git warehouse history. `.recovery/` is gitignored and absent from frontend build assets. Original source archives, reviewed CSV observations and last-good data remain governed by the existing collector protections.

## Testing and operations

- `python -m unittest discover -s tests -p test_self_heal.py -v` covers boundaries, reflection/path rejection, secret redaction, exact CI/review binding, replacement-run escalation, merge races, and a real recorded Vertex mixed-column replay/regression.
- `npm run check` and `npm run test:e2e` retain the full existing suites.
- A real paid AI repair/review requires the dedicated API key and enabling the variable. Offline tests/mocks are not described as successful real AI repair runs.
- To inspect: open the recovery issue and linked workflow, repair PR, exact-head CI and replacement run. If recovery stops, do not repeatedly relaunch the same run; review the reason, fix configuration/semantics manually, and retry ordinary collection.
- To disable: set `ENABLE_SELF_HEALING=false`, cancel any active recovery, and remove/rotate `OPENAI_API_KEY` if appropriate. Normal daily collection continues unchanged.
