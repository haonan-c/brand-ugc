# XHS Topic Radar Workflow Contract

## External seam

The single runtime interface is `scripts/topic_radar.mjs`. All commands emit JSON to stdout and progress/errors to stderr. Callers do not import `lib/` modules directly.

## State machine

```text
unconfigured
  → configured
  → previewed (three bounded suggestion requests; awaiting approval)
  → collecting (explicit --approve required)
  → awaiting_finalize
  → completed
```

Failures are stored as `failed` runs where a run has already been created. Partial search/comment failures are recorded in the pending pack and do not erase successful evidence.

## Commands

| Command | Paid requests | Purpose |
|---|---:|---|
| `setup` | 0 | Save industry, lookback, queries, audiences, quotas, and hard limits |
| `key set/status/clear` | 0 | Secure local TikHub credential management |
| `preview` | normally 3 | Official pricing/balance preflight and autocomplete preview |
| `collect --approve` | at most remaining 24 | Search notes, sample comments, write evidence pack |
| `finalize` | 0 | Validate topics and write reports |
| `status` / `report` / `config` | 0 | Inspect local state |

`collect` without `--approve` must stop before loading a plan, credential, or making a paid request. A plan expires on the next local date and after any configuration-signature change.

## Cost and request safety

- Fetch current prices from TikHub's official pricing endpoint before discovery.
- Check available balance/free credit against the bounded full-run estimate.
- Default hard cap: 27 business requests.
- Default hard cap: US$0.30 estimated cost.
- Charge each attempted business request against both caps before calling it.
- Pace business requests using the configured minimum interval.
- Never downgrade or bypass a cap after user approval.

Administrative pricing/balance requests are not included in the business-request count but remain authenticated calls.

## Credentials and logs

Credential precedence is environment variable, then the protected local credential file. The local directory is mode `0700`; the file is mode `0600`. The CLI accepts a new key only through stdin. Error cleanup redacts authorization values and `TIKHUB_API_KEY` assignments.

Do not print raw authorization headers, full keys, Base64 data, or temporary URLs.

## Local data

All workflow data lives under `<brand-workspace>/.brand_ugc/topic-radar/`:

```text
config/topic-radar.json
data/topic-radar.sqlite
data/raw/YYYY-MM-DD/
data/plans/<plan-id>.json
data/pending/<run-id>.json
data/drafts/<run-id>-topics.json
reports/YYYY-MM-DD.md
reports/YYYY-MM-DD.json
reports/latest.md
```

Same-date cache reuse requires a matching configuration signature. `--force` is an explicit paid refresh, not a default.

## Evidence integrity

TikHub note IDs and xsec tokens are normalized into evidence URLs during collection. Finalization accepts only exact URL strings already present in the pending pack. Agents must never rebuild, shorten, normalize, or remove query parameters from an evidence URL.
