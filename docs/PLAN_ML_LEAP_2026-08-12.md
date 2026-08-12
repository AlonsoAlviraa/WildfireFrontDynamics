# PLAN_ML_LEAP — salto métricas / eval / modelo (2026-08-12)

**Repo:** AlonsoAlviraa/WildfireFrontDynamics  
**Product:** `clm_ensemble_v34` (lab) · **No** field_ops fusion  
**Quién:** Alonso (datos/promote) · Data Steward · ML Lab · Research · eng A/B solo donde paths toquen docs/CI  
**SSOT gates:** `docs/CURRENT_STATE.md` · `docs/ML_PRODUCT_GO_STATUS.json` · `docs/ML_PRODUCT_SCORECARD.json`  
**Claims:** `docs/CLAIM_BOARD_ML_LEAP_2026-08-12.md`  
**Companions:** `docs/B4_B5_UNBLOCK_CALENDAR.md` · `docs/DATA_ANCHOR_SSOT.md` · `docs/BOTTLENECKS_B1_B6_STATUS.md`

## Verdict

El salto ML **no** es retrain/transformer ahora. Es **REQUEST_DATA (Hellín / 2º IF) → eval honesty (E1) → (opcional) selective/FNR curves**; modelo **v35** solo tras **nuevo IF** + lift humano de FREEZE (parcial o total).

## Rails (no negociables)

- `FREEZE_ML_AND_REQUEST_DATA` · Tobarra KEEP reopen = **false** (KILL)
- `field_ops` ML fusion **OFF**
- `GO_Q` **partial** (nunca inventar complete)
- IoU ≠ ROS / Vp · catalog holdout **0.8963** = provenance only
- No inventar grade A / GO_MES+ / métricas no medidas
- No revive `#10` / secret-bearing bases

## Baseline lab (frozen evidence — no re-measure in this doc)

| Metric | Value | Nota |
|--------|-------|------|
| U1 TEST mean IoU | ~0.857 (n=200) | Mask holdout; not live / not ROS |
| Selective IoU @80 | ~0.903 | Ranking skill; not “drop 20% of fire” sell |
| ECE patch (TEST) | ~0.153 | Honest sellable cal residual |
| Nested VAL ECE | ~0.058 | **Not** TEST; do not pitch as field cal |
| Catalog holdout IoU | 0.8963 | Provenance only |
| Tobarra LOFO IoU | ~0.49 | Domain/data gap; KEEP thrash = NO_GO |
| Sealed LOFO pitch | ~0.79 | Non-Tobarra narrative under FREEZE |

## Consensus (ML Lab + Data Steward + Research)

| Tema | Acuerdo |
|------|---------|
| Techo Tobarra | Data/domain; no epochs on same mix |
| Orden | **Data → Eval → Model** |
| Steal (0 GPU) | Selective risk–coverage · TEST ECE honesty · FNR@budget → GO/HOLD/ABSTAIN |
| Vanity | 0.8963-as-live · AUROC-alone · IoU-as-ROS · nested ECE as field |
| Arch leap under FREEZE | **Contradicted** (Swin/FireCast ≠ leap) |

---

## Program packs → PRs (shippable)

### Pack D0 — REQUEST_DATA / Hellín (humano + Data)

**PR-D0 (docs/data honesty, no promote automatic):**  
`docs(data): ML LEAP REQUEST_DATA pack + Hellín cite checklist`  
**Branch:** `docs/ml-leap-d0-request-data`

**Done-when:**
- [ ] Lista P0/P1/P2 en docs (Hellín PDF+KMZ, Cardoso/2º IF, GeoTIFF ≥3 scenes, rights)
- [ ] Checklist cite→promote Hellín (H1–H7); status sigue `pending_external` hasta Alonso
- [ ] `check_release_flags` PASS; no flip anchors sin OK escrito

**Non-goals:** FOI send · Hellín `confirmed` sin cite · retrain

**Humano Alonso (fuera PR):** copiar PDF+KMZ a árbol auditable; OK promote; outreach GEACAM.

---

### Pack E1 — Eval repro (ML Lab / eng B)

**PR-E1:** `docs+scripts(ml): U1 TEST one-shot + scorecard validate (frozen cal)`  
**Branch:** `feat/ml-leap-e1-eval-oneshot`

**Done-when:**
- [ ] Doc comandos: `check_release_flags` → smoke ML → `eval_ml_uncertainty_u1 --split test` + frozen cal → `validate_ml_scorecard`
- [ ] Explicit: **no** overwrite `uncertainty_calibration_v1.json` under FREEZE; SKIP-without-weights ≠ honesty green
- [ ] Compare latest scorecard vs `docs/ML_PRODUCT_SCORECARD.json` (drift note)

**Non-goals:** refit cal on TEST · promote script flip · fusion ON

---

### Pack E1b — Eval leap lite (Research / eng, 0 GPU)

**PR-E1b:** `docs(ml): selective risk–coverage + FNR@budget method note`  
**Branch:** `docs/ml-leap-e1b-selective-fnr`

**Done-when:**
- [ ] Method note: curves @50/80/90 + Δ vs random; FNR@budget → GO/HOLD/ABSTAIN (not dispatch)
- [ ] Claim board L1–L8 enforced in PR body
- [ ] No new architecture / no retrain

---

### Pack P1 — Perf (después E1)

**PR-P1:** `chore(ml): decide/serve latency p50/p95 measure path`  
**Branch:** `chore/ml-leap-p1-latency`

**Done-when:** script/doc `measure_decide_api_latency` (o equivalente); números **medidos** o “not run”; budget hint metrics-only (p.ej. p95 500ms) sin inventar.

---

### Pack M1 — Model lab (data-gated; requiere Alonso)

**Gate:** nuevo IF class on-disk + scorecard path **o** OK escrito lift parcial FREEZE.  
**PR-M1 (solo entonces):** hipótesis H1 mix / H2 cal / H3 arch+multi_if — nuevo `product_id` candidato; done-when **vs v34 TEST**; KEEP Tobarra sigue false salvo flip humano aparte.

**Non-goals under FREEZE:** M5 v35 GO · Swin/FireCast as default leap · field fusion ON

---

## Claim board (enforce)

| ID | Status | Sell |
|----|--------|------|
| L1 | supported (lab honesty) | YES-with-scorecard |
| L2–L3 | supported (literature) | NO as WFD SOTA |
| L4–L5 | contradicted | **NO** |
| L6–L8 | inventable-only-with-scorecard | NO until scorecard+Alonso |

## Kill list

- Tobarra KEEP thrash · TEST refit cal · fusion ON · IoU→ROS  
- Catalog 0.8963 as live · invent grade A / GO_MES+  
- “Transformer = leap” under FREEZE · FOI spam / CyL silence breach

## Orden anti-choque

```
1) PR-D0 docs/data (Data / Alonso bytes)
2) PR-E1 eval one-shot (ML Lab)  ||  PR-E1b method note (Research) — disjoint paths
3) PR-P1 latency
4) PR-M1 only after data gate + Alonso
```

## Definition of Done (ML LEAP phase 1)

- [ ] REQUEST_DATA pack + Hellín checklist in `docs/`
- [ ] E1 one-shot documented; frozen-cal TEST path clear
- [ ] Selective/FNR method note + claim board in `docs/`
- [ ] No gate flips; FREEZE intact
- [ ] Phase 2 (M1) explicitly blocked until new IF / lift
