# 007-port eval baseline

Snapshot of `backend/artifacts/eval_runs/{advanced,advanced-engine}.jsonl`
taken on `fix/007-citation-guard`, **post-fix** (after
`pipeline/grounding.py::filter_ungrounded_cites` landed — see `COMPARISON.md`
for the pre-fix numbers and the full before/after). Both runs on the same
commit, same fixture-backed closet (`adapters/closet_fixture.py`), same
golden set (24 cases), `--strategies advanced`, run 2026-07-31. Gitignored at
the source (`backend/artifacts/eval_runs/`), so this copy is the durable
record — promoted by hand, matching the `010-engine` precedent this
directory sits alongside.

This is Feature 007's own port-verification measurement, not a design-change
comparison: the reference point is `../010-engine/COMPARISON.md`, the last
measurement taken on the legacy prototype before this port. See
`COMPARISON.md` in this directory for the full metric-by-metric breakdown
against that baseline, including the pre-fix run (overwritten in place by
this post-fix run — its numbers are preserved in `COMPARISON.md`'s text, not
as a separately retained JSONL file) and every delta traced to a specific
case ID rather than averaged.

`hallucinated_items` was 0 across both files, on every case, pre- and
post-fix — the item-level grounding guarantee
(`pipeline/grounding.py::verify_outfit_grounding`) was never in question;
issue 1 was specifically about the citation-level guarantee, which
`all_cites_grounded` had checked as a metric since 007 but which nothing in
the pipeline enforced until this fix.
