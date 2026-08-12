# Deep-verify claim pack — Product SPA Industrial C2

Compact claim set for claim-by-claim verification against the WildfireFrontDynamics repo.
Sources: docs/CURRENT_STATE.md, docs/APP.md, docs/AUDIT_AND_PR_PLAN_SPA_C2_20260811.md, wildfire_front/product/*, scripts/check_release_flags.py, tests/*.

## Claims

1. GO_MES is true in the product gates documented in docs/CURRENT_STATE.md.
2. GO_Q is partial (not fully true) in docs/CURRENT_STATE.md and requires H1 human demo+acta.
3. field_ops ML live fusion is OFF as a non-negotiable product rail.
4. Product code must not invent GO_Q true without H1 (go_q invent forbidden).
5. The product SPA is opened with `python -m wildfire_front app` and aliases `spa` and `console` map to app.
6. The SPA industrial C2 shell uses dark background token `#0B1220` in HTML/CSS.
7. The SPA shows three primary acts labeled Estado, Decidir, and Acta (primary-acts).
8. Dual-mode UI supports Fácil and Pro modes; simple mode hides advanced CLI elements.
9. Fire catalog entries include rebuild_cmd, map_cmd, status_cmd, decide_cmd, and acta_cmd fields.
10. `app --serve` binds only to loopback 127.0.0.1 by default and refuses non-loopback hosts.
11. SPA static file handler returns HTTP 403 for path traversal attempts outside the output dir.
12. Function is_loopback_http_url accepts 127.0.0.1 and localhost but rejects hosts that only start with 127.0.0.1 as a prefix (e.g. 127.0.0.1.evil.example).
13. Optional `--bridge-decide` only keeps loopback URLs; non-loopback bridge URLs are disabled/stripped.
14. When SPA is served with bridge configured, browser can call same-origin path `/bridge/v1/decide` which proxies to serve-decide.
15. Multi-fire pack is available via `--all-fires` or `--pack-fires` with a hard maximum of 8 fires.
16. scripts/check_release_flags.py includes SPA industrial marker checks and fails release if GO_Q invent is allowed or fusion is ON.
17. Tests exist for product SPA: tests/test_product_app.py, tests/test_spa_layout.py, tests/test_app_spa_security.py, tests/test_check_release_flags.py.
18. Makefile target `test-spa` runs the SPA industrial test pack.
19. Tobarra KEEP process is KILL (do not reopen without new data) as documented in CURRENT_STATE / bottlenecks.
20. START_HERE or PORTAL third-party demo path points primarily to the product SPA app surface, with commander marked legacy.
21. Product action catalog exposes at least 30 CTAs with plain-language fields.
22. Role switcher supports operator, field, lab, and decision roles in the SPA payload/UI.
23. Missing SPA output directory for --serve causes non-zero CLI exit (exit code 2).
24. ABSTAIN is documented as intentional product behaviour, not a crash.
25. IoU is not ROS and FIRMS NRT hotspots are not official perimeter, as honesty rails on the SPA/product.
