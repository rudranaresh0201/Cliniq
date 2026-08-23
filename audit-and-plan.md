# Cliniq — Repo Audit, Fixes Applied

## Fixed and pushed (2026-08-23)

- **Timing-attack-vulnerable admin key check**: `backend/main.py`'s
  `/api/evaluation/run` compared `X-Admin-Key` with plain `!=`. Same class of
  issue as prguard's webhook signature check — a plain `!=` exits early on
  the first mismatched character, giving an attacker a timing signal to
  guess the secret byte by byte. Fixed with `hmac.compare_digest`.

## Verified real (not just claimed)

- **Emergency red-flag detection is 100% deterministic** — `backend/safety/
  redflags.py::check_emergency` is a pure keyword-list scan, zero LLM calls.
  Correctly matches the README's "before any LLM call" claim, and is the
  right design choice for something this safety-critical: a hardcoded
  keyword miss is bad, but a probabilistic LLM judgment call on "is this an
  emergency" would be worse and unpredictable.
- **PubMedBERT embeddings are real** — `EMBEDDING_MODEL =
  "pritamdeka/PubMedBERT-mnli-snli-scinli-scitail-mednli-stsb"` in
  `config.py` (repo root), loaded via `SentenceTransformer(EMBEDDING_MODEL)`
  in `backend/memory/rag.py`. (First-pass grep of only `backend/` missed
  this and would have wrongly flagged it as fabricated — worth remembering
  to check the repo root, not just the obvious subfolder, before calling
  something a gap.)
- **The "9-stage pipeline" in the README is real and matches
  `backend/main.py::_run_pipeline` exactly** — safety check, cache lookup,
  clinical reasoning, classify+plan, fetch→evaluate retry loop, synthesis,
  faithfulness+contradiction checks, cache storage. Faithfulness scoring
  genuinely gates on a threshold (`< 0.4` triggers a `reliability_warning`
  in the response), not just a cosmetic score.
- **`agents/pipeline.py`'s "6 stages" is a second, separate pipeline**
  (`ClinIQPipeline`, serving `/api/analyze/v2`) — patient/case management
  with monitoring plans, escalations, and timeline persistence, not a
  contradiction of the README's 9-stage diagram. Two legitimately different
  subsystems serving two different endpoints, not a lie.
- **PERSIST stage is genuinely non-fatal** — every persistence call
  (`_persist_risk`, `_persist_timeline`, `_persist_monitoring`,
  `_persist_tasks`, `_persist_agent_note`) is independently wrapped in its
  own try/except, and `run()` always returns the synthesis even if every
  persist call fails. Matches the README's explicit claim.
- **Admin key gate itself was real** (just not constant-time) — genuinely
  raises 403 without a valid key, not decorative.
- **Live demo**: frontend (Vercel) responds 200. Backend (Render) did not
  respond even after a 60s retry — most likely a suspended free-tier
  instance rather than a code defect, but worth checking/waking before
  presenting this project live.

## Still open, not fixed this pass

1. **Zero test files anywhere in the repo.** Only CI present is
   `.github/workflows/deploy.yml` (deployment automation), nothing runs
   tests on push/PR. Same gap found in every project audited this session
   — highest-value next step if this project gets presented in an
   interview, given `backend/evaluation/metrics.py` already exists and
   could anchor a real regression-tested eval suite instead of only a
   manually-triggered `/api/evaluation/run`.
2. **`chroma_db_backup/` sitting in the repo root** — not yet checked
   whether this is meant to be committed (a real backup snapshot) or
   accidental (a local dev artifact that shouldn't be in git). Worth a
   quick look before presenting.
3. Backend not verified live end-to-end this pass (Render instance
   unreachable) — the pipeline code was verified by reading, not by an
   actual live request/response round trip like agentic-rag's cross-encoder
   and sandboxing fixes were. Worth doing if time allows before an
   interview where this project comes up.
