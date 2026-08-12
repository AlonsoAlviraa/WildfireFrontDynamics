# Deep-verify report — Product SPA C2 claim pack

| Metric | Value |
|--------|-------|
| **total** | 57 |
| **supported** | 57 |
| **contradicted** | 0 |
| **unverifiable** | 0 |
| **claimErrors** | 0 |
| audit high | 57 |
| audit medium | 0 |
| audit low | 0 |

## Scope

Input: docs/VERIFY_PACK_PRODUCT_SPA_C2.md (compact claim set for product SPA industrial C2 + gates).
Not a byte-for-byte scan of every .md/.py in the monorepo (first full dump hit Windows ENAMETOOLONG).
Pack covers CURRENT_STATE, APP, audit plan, product SPA modules, release flags, honesty rails.

## Verdict

**All extracted claims supported after adversarial audit.** Zero contradicted, zero unverifiable.

## Contradicted / unverifiable

None.

## Supported claims (sample)

- **c1** (audit=high): GO_MES is true in the product gates documented in docs/CURRENT_STATE.md.
  - source: docs/CURRENT_STATE.md:14,19
- **c10** (audit=high): Dual-mode UI supports F├ícil and Pro modes.
  - source: wildfire_front/product/app_spa_html.py (lines 3, 355-357, 549-560); wildfire_front/cli_app.py (lines 23-26); docs/APP.md (dual-mode F├ícil/Pro)
- **c11** (audit=high): Simple (F├ícil) mode hides advanced CLI elements.
  - source: wildfire_front/product/app_spa_html.py:42,355-357,549-552,947,1014; wildfire_front/cli_app.py:190-193; wildfire_front/product/app_spa.py:40,331-332
- **c12** (audit=high): Fire catalog entries include a rebuild_cmd field.
  - source: wildfire_front/product/fire_catalog.py:89; tests/test_product_app.py:81-85; wildfire_front/product/app_spa.py:300
- **c13** (audit=high): Fire catalog entries include a map_cmd field.
  - source: wildfire_front/product/fire_catalog.py:90; tests/test_product_app.py:82-85
- **c14** (audit=high): Fire catalog entries include a status_cmd field.
  - source: wildfire_front/product/fire_catalog.py:78-94; tests/test_product_app.py:82-85
- **c15** (audit=high): Fire catalog entries include a decide_cmd field.
  - source: wildfire_front/product/fire_catalog.py:78-93; tests/test_product_app.py:82-85; wildfire_front/product/app_spa.py:303
- **c16** (audit=high): Fire catalog entries include an acta_cmd field.
  - source: wildfire_front/product/fire_catalog.py:93; tests/test_product_app.py:82-85
- **c17** (audit=high): `app --serve` binds only to loopback address 127.0.0.1 by default.
  - source: wildfire_front/cli_app.py:409,606-634,142-148
- **c18** (audit=high): `app --serve` refuses non-loopback hosts.
  - source: wildfire_front/cli_app.py:381-394,612-619; tests/test_app_spa_security.py:84-102
- **c19** (audit=high): The SPA static file handler returns HTTP 403 for path traversal attempts outside the output dir.
  - source: wildfire_front/cli_app.py:_SafeSPARequestHandler (do_GET/do_HEAD/_safe_path); tests/test_app_spa_security.py::test_handler_path_traversal_403_and_loopback_200
- **c2** (audit=high): GO_Q is partial (not fully true) in docs/CURRENT_STATE.md.
  - source: docs/CURRENT_STATE.md lines 14, 21, 86
- **c20** (audit=high): Function is_loopback_http_url accepts host 127.0.0.1.
  - source: wildfire_front/product/app_spa.py:47-65; tests/test_app_spa_security.py:42
- **c21** (audit=high): Function is_loopback_http_url accepts host localhost.
  - source: wildfire_front/product/app_spa.py:47-65; tests/test_app_spa_security.py:43
- **c22** (audit=high): Function is_loopback_http_url rejects hosts that only start with 127.0.0.1 as a prefix (e.g. 127.0.0.1.evil.example).
  - source: wildfire_front/product/app_spa.py:47-65; tests/test_app_spa_security.py:41-48

…and 42 more supported claims.

## Themes confirmed

- Gates: GO_MES true · GO_Q partial · no invent GO_Q · fusion OFF
- SPA C2: #0B1220, primary acts Estado/Decidir/Acta, Fácil/Pro dual-mode
- Catalog cmds: rebuild/map/status/decide/acta
- Serve: loopback-only, path traversal 403
- Bridge loopback + same-origin proxy path
- Multi-fire pack cap 8, release flags SPA markers, tests pack present
- Honesty: ABSTAIN feature, IoU ≠ ROS, FIRMS ≠ perimeter

