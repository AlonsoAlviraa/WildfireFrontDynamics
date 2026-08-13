# Data anchor SSOT — O1 honesty

> **As of:** 2026-08-12 (Agent B W1)  
> **Canonical file:** `data/infocam_anchors.json`  
> **Rule:** only `status: confirmed` with explicit source counts for O1/O5 / grade A.  
> **Do not invent Vp/ha.**  
> **Human promote only:** Alonso (or designated owner) — agents never flip `pending_external` → `confirmed` without cite.

## Confirmed (main tip)

| fire_id | Vp | ha | source |
|---------|----|----|--------|
| `tobarra_20240802` | 7.0 | 39 | INFOCAM 2024 parte operativo |

## Pending external (not GO)

| fire_id | Notes |
|---------|--------|
| `hellin_2024` | **SSOT = pending_external.** Any demo script / spa note saying Hellín “confirmed Vp=50” is **not** SSOT until this JSON is updated with cite + human OK. |
| `cardoso_2025` | pending — request Vp/ha Observatorio/INFOCAM (preferred 2nd-anchor ask if outreach is live) |
| `la_estrella_acom1_2024` | pending |
| `retuerta_2025` | pending (+ QA flag — do not promote while flagged) |

## Decision (BK-5 / GO_MES+)

Until Alonso promotes with a **literal cite**: **keep Hellín pending**. Prefer Cardoso as 2nd-anchor ask if that is the live outreach thread. GO_MES+ stays **false** without a 2nd grade A confirmed anchor.

---

## Cite → promote checklist (docs only; human gate)

Use this checklist **before** any PR that changes `data/infocam_anchors.json` for a pending fire. Agents may prepare the PR body; **human merges only after all boxes**.  
Hellín IDs **H1–H7** (ML LEAP D0): see also `docs/ML_LEAP_REQUEST_DATA.md`.

### Required evidence (H1–H7)

1. **H1 Literal cite** — quote or scan from INFOCAM / Observatorio / official parte (date, fire name, Vp and/or ha). No “approx” / hearsay / slide screenshots without numbers.
2. **H2 Units match schema** — `vp_m_min` in m/min, `area_ha` in ha; nulls only while pending.
3. **H3 fire_id stable** — same key as inventory (`hellin_2024`, not a new alias).
4. **H4 source string** — non-empty, attributable (who / which bulletin).
5. **H5 status flip** — only `pending_external` → `confirmed` in the same PR that fills `vp_m_min` / `area_ha` / `source`.
6. **H6 Alonso OK** — written on PR / acta; agents do not merge promote. QA clean if flagged (e.g. Retuerta).
7. **H7 No ML retrain** — FREEZE_ML: promote ≠ reopen Tobarra KEEP. After promote, update CURRENT_STATE 2nd grade A honestly; **do not** set GO_Q true.

### Forbidden shortcuts

- Copying Vp/ha from SPA demo notes, pitch decks, or third-party chat without official cite.
- Setting `status: confirmed` while `vp_m_min` / `area_ha` / `source` remain null.
- Promoting Hellín to close a sales story or demo dry-run.
- Treating inventory “listo ops” in `DATA_INTAKE_STATUS.md` as confirmed anchor.

### No cite = no promote (W3-B)

There is **no official cite today**. Engineering **must not** open a promote PR.

- `scripts/refuse_promote_without_cite.py` exits **0** while only Tobarra is `confirmed`.
- `--attempt-promote --fire-id hellin_2024` exits **1** with `error: no cite = no promote`.
- `can_promote_to_confirmed` refuses H1=0 and null vp/ha/source. `force` never bypasses.
- Cite bytes, if they arrive, go to gitignored `data/real_if/<fire_id>/cite/` via `scripts/copy_cite_to_real_if.py` (missing file → exit 1). Copy ≠ promote.

### After promote (human)

```bash
python scripts/check_release_flags.py   # still PASS; GO_Q partial
pytest tests/test_data_anchor_honesty.py tests/test_check_release_flags.py -q
```

If only Hellín becomes confirmed and Tobarra remains, GO_MES+ may still be false until process/scorecard criteria are met — update narrative, do not invent gates.

---

## Related

- `docs/DATA_INTAKE_STATUS.md` — inventory; may overstate stacks on thin clones
- `docs/CURRENT_STATE.md` — GO_MES+ still open on 2nd grade A
- `scripts/check_release_flags.py` — fusion ON (human 2026-08-13) + GO_Q partial rails
- `tests/test_data_anchor_honesty.py` — guards against silent promote
