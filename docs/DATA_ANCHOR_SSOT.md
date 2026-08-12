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

### Required evidence

1. **Literal cite** — quote or scan reference from INFOCAM / Observatorio / official parte (date, fire name, Vp and/or ha). No “approx” / hearsay / slide screenshots without numbers.
2. **Units match schema** — `vp_m_min` in m/min, `area_ha` in ha; nulls only while pending.
3. **fire_id stable** — same key as inventory (`hellin_2024`, not a new alias).
4. **source string** — non-empty, attributable (who / which bulletin).
5. **status flip** — only `pending_external` → `confirmed` in the same PR that fills `vp_m_min` / `area_ha` / `source`.
6. **QA clean** — if fire has QA flag (e.g. Retuerta), resolve or explicitly waive in PR body; default = do not promote.
7. **CURRENT_STATE** — after promote, update 2nd grade A / GO_MES+ notes honestly (Agent B ownership); do **not** set GO_Q true.
8. **No ML retrain** — FREEZE_ML: promote anchor ≠ reopen Tobarra KEEP retrain.

### Forbidden shortcuts

- Copying Vp/ha from SPA demo notes, pitch decks, or third-party chat without official cite.
- Setting `status: confirmed` while `vp_m_min` / `area_ha` / `source` remain null.
- Promoting Hellín to close a sales story or demo dry-run.
- Treating inventory “listo ops” in `DATA_INTAKE_STATUS.md` as confirmed anchor.

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
- `scripts/check_release_flags.py` — fusion OFF + GO_Q partial rails
- `tests/test_data_anchor_honesty.py` — guards against silent promote
