# Publishing snapshots after collection

## Authorization and gate policy

After reviewing PR #2, the user approved its merge and initial manual release,
and explicitly approved automatic data-only publishing after that release verifies.
The authorized publishing settings are `ENABLE_PAGES=true` and
`ENABLE_COLLECTION_PUBLISH=true`. Apply the latter only after initial-release
verification, following the activation sequence below. Self-healing stays
`ENABLE_SELF_HEALING=false`; no paid service, deposit, worker or inference is used.

Code/configuration/documentation releases remain explicitly authorized manual
`main` dispatches. Automatic publication is a narrower permission: **data-only
updates to an already published code version**. A push alone does not publish,
and a later collection cannot silently release previously unpublished code.

## Pipeline and exact-tree checks

1. `collect.yml` runs its offline parser/documentation preflight and strict collection.
   Together's intentional document-only inventory mode counts as collection, not a
   provider failure. Actual partial failures still retain valid updates and health,
   then fail at **Surface collector failures**. Failed/cancelled collection never
   enters automatic publishing.
2. The collector commits valid `data/` updates and records the **actual pushed SHA
   after any rebase**. Its successful job can call reusable `deploy.yml` only from
   `main`, with both publication gates enabled. No secrets are inherited.
3. The resolver checks out trusted caller/dispatch code, with no persisted checkout
   credentials. It verifies a literal 40-character SHA, current `main` tip, and the
   latest successful `github-pages` deployment baseline. Automatic publication is
   skipped if the baseline is unknown, main advanced, history would roll back, or
   any changed path is outside `data/`. Non-data changes require manual release.
   API work is bounded and metadata/API failures fail closed.
4. The build checks out that exact resolved SHA, installs pinned-lockfile npm and
   Python requirements, runs `npm run check` (including production build), then
   browser/accessibility checks. The build job allows 75 minutes for three complete
   historical projections (unit tests, production build and browser-server startup),
   dependency setup and the remaining checks. Each verifier retains its 15-minute
   bound; full-corpus test setup and browser-server startup retain 20-minute bounds.
   Publishing receives no collector keys. Only the
   static reviewed allowlist, small build metadata and validated native projections
   enter the Pages artifact; never warehouse archives, proofs or raw responses.
5. The deploy job depends on successful resolution and build. It alone gets an
   OIDC token; Pages deployment uses the pinned action and `github-pages` environment.
   All Pages paths share non-cancelling concurrency. Manual dispatch remains pinned
   to its dispatch SHA, not whatever main happens to contain later.

The automatic build may execute newly collected **data**, never candidate scripts
from a failed/PR artifact. The trusted resolver's data-only comparison constrains
which code version can be released. GitHub's deployment record can identify the
caller SHA for reusable runs; its code version is still the baseline, while the
public `publication.json` identifies the exact built data snapshot SHA.

## Freshness metadata

Vite generates `publication.json` in development and production:

- `data_collected_at`: the included `status.json` run timestamp;
- `built_at`: when this build was made (development shows session start);
- `commit_sha`: exact built snapshot if supplied by publishing, otherwise null;
- `mode`: development, local build, manual release or automatic data update.

The UI labels **Collected through** separately from **Site built**. Build time is
not a claimed deployment time or proof that every retained quote was refreshed.
Mismatched status/metadata fails dataset loading rather than presenting a mixed
snapshot as complete. Everything loads from the same static origin; there are no
runtime provider/GitHub API calls. Per-offer stale/failed labels remain independent.

## Activation after review

The user has authorized this initial release and data-only activation. Follow the
sequence below; the guide alone is not authorization for unrelated future releases:

1. Review and merge the PR after CI passes.
2. Obtain/confirm authorization for the initial manual code release. Dispatch
   `gh workflow run deploy.yml --repo yogenpro/token3 --ref main` and verify the
   successful run, public `publication.json`, data timestamps and native assets.
3. Deliberately enable the standing data-only permission:
   `gh variable set ENABLE_COLLECTION_PUBLISH --repo yogenpro/token3 --body true`.
4. Deliberately dispatch and verify a complete strict collection after merge, or
   inspect the next daily run. Verify its automatic release and the public SHA.
   Local mocks/dry-runs are not proof that this hosted publishing path ran.

To stop automatic updates, set `ENABLE_COLLECTION_PUBLISH=false`; collection
continues. Do not bypass failed checks or auto-publish partial data to restore
freshness. No automatic rollback to older snapshots is implemented. Future code
changes intentionally stop automatic data publication until an authorized manual
release establishes the new published baseline.
