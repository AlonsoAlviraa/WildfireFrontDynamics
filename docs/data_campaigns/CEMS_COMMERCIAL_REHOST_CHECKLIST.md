# CEMS commercial rehost checklist

> **Not a legal opinion.** Lab-internal guidance for product packaging.  
> **Gate file:** [`cems_commercial_rehost_gate.json`](cems_commercial_rehost_gate.json)  
> **Rights sheet:** [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md)  
> **As of:** 2026-08-13

`commercial_rehost_ok` stays **`false`** until Alonso / legal light signs. No silent commercial claim.

## Reg. (EU) 2021/696 — obligations for commercial redistribution

Copernicus Service Information (including EMS Rapid Mapping products used in LATAM/AU packs) is governed by **Regulation (EU) 2021/696** and the [CEMS On-Demand T&C](https://mapping.emergency.copernicus.eu/terms-and-conditions/):

| Obligation | Lab practice |
|------------|--------------|
| Free, full, open access (no warranty) | Products are **as-is**; no fitness claim for tactical dispatch |
| Reproduce / distribute / adapt allowed under T&C | Always **inform recipients of the source** |
| No IP transfer to user | EU ownership of source data remains |
| Art. 53 restricted products | **Not** used in this campaign (public vector zips / viewer JSON only) |
| Third-party layers | Different terms — not train labels here |
| Commercial product rehost | Needs **human/legal sign-off** beyond provisional `lab_ok` |

### Required attribution block (any public or paid surface)

```
Contains modified Copernicus Emergency Management Service information
(2019, 2021, 2023, 2024). Activations: EMSR408, EMSR500, EMSR647, EMSR715
(as applicable to the shipped pack).
Source: https://mapping.emergency.copernicus.eu/
© European Union, Copernicus EMS — information provided as-is, no warranty.
Proxy perimeter ≠ national cadastre / O2 España / CONAF official.
```

If Sentinel-2 is included:

```
Contains modified Copernicus Sentinel-2 data ([year]).
Accessed via Element84 Earth Search STAC.
```

## What needs human / legal sign-off

- [ ] Written OK for **commercial product** use of CEMS-derived packs (not only lab experiments)
- [ ] Attribution text present on every paid download / CDN landing / SaaS export
- [ ] Confirm no Art. 53 restricted product slipped into the ship bundle
- [ ] MapBiomas CC-BY and NAFI citation if those packs are rehosted
- [ ] Decide rehost matrix path (gitignored multi-GB vs CDN) and record URL policy
- [ ] Flip `commercial_rehost_ok` to `true` **only** in `cems_commercial_rehost_gate.json` with signer + UTC

Until then: packaging scripts must **fail closed** or **warn** and refuse silent commercial claim.

## Product rehost matrix

| Path | Allowed when `commercial_rehost_ok=false` | Notes |
|------|-------------------------------------------|-------|
| Lab git tree `data/open_if/latam_au/**` multi-GB rasters | **gitignored** only; never commit rasters | Local / CI materialize |
| Internal artifact zip for offline lab | OK if attribution + `lab_ok` provisional | Not a public product claim |
| Public CDN / paid download of CEMS-derived GeoTIFF stacks | **Blocked** until sign-off | Script exit ≠ 0 |
| SaaS API serving CEMS masks as “product data” without cite | **Blocked** | Attribution mandatory even after OK |
| Thumbnail / low-res figure with attribution | Lab OK | Still not O2 / CONAF |

## Engineering gate

```bash
python scripts/check_cems_commercial_rehost.py
# exit 0 — gate file present, commercial_rehost_ok=false is honest; no rehost attempt

python scripts/check_cems_commercial_rehost.py --require-commercial-rehost
# exit 1 while commercial_rehost_ok=false (packaging path fail-closed)

python scripts/check_cems_commercial_rehost.py --attempt-cdn-rehost
# exit 1 while flag false — refuses silent commercial rehost
```

## Rails

- Does **not** flip GO_Q, FREEZE, or field_ops fusion.
- Lab `lab_ok` provisional ≠ commercial rehost OK.
- No invented transfer IoU from CEMS packs.
