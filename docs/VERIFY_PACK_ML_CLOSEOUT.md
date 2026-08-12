# Deep-verify claim pack — ML lab closeout

Compact claims for verification against in-repo ML boards/stamps.
Sources: `docs/GOAL_ML_CLOSEOUT.md`, `docs/ml/README.md`, `docs/CURRENT_STATE.md`,
`outputs/ml_eval/lab_loop/ML_CLOSEOUT_DECISION.json`,
`outputs/ml_eval/lab_loop/ML_CLOSEOUT_CHECKER.json`.

## Claims

1. ML closeout decision stamp exists at `outputs/ml_eval/lab_loop/ML_CLOSEOUT_DECISION.json`.
2. ML closeout decision is `FREEZE_ML_AND_REQUEST_DATA`.
3. ML closeout stamp has `met` true (goal met for thrash freeze path).
4. ML closeout rails set `field_ops_allow_ml_live_in_fusion` to false (field fusion OFF).
5. ML closeout rails set `iou_is_not_ros` to true.
6. ML closeout rails set `ml_product_go` true as lab-only (not field fusion).
7. ML closeout rails set `tobarra_keep_reopen` to false (Tobarra KEEP KILL held).
8. Sealed champion config in closeout is `exact_force_ema_long` with documented mean near 0.7878.
9. Weather champion path era5_long is frozen as lab weather spatial, not field fusion.
10. Kill list includes Tobarra KEEP reopen and larger U-Net default thrash.
11. `docs/GOAL_ML_CLOSEOUT.md` defines FREEZE_ML / REQUEST_MORE_DATA / CEILING outcomes.
12. Checker stamp `outputs/ml_eval/lab_loop/ML_CLOSEOUT_CHECKER.json` reports met true for the freeze decision.
13. CURRENT_STATE documents ML closeout FREEZE_ML_AND_REQUEST_DATA and fusion OFF.
14. Product must not claim sealed mean +0.05 without board evidence (closeout ceiling rules).
15. Lab `ml_product_go` true does not authorize field_ops ML live fusion ON.
