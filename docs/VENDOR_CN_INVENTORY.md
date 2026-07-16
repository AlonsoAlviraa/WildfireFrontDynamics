# Inventory: downloaded fire-spread / CN-adjacent code and data

**Generated:** 2026-07-16  
**Root:** `_vendor_cn/` (gitignored local vendor cache — not committed to remote)  
**Attempt log:** see scratch / `download_attempts.log`  
**Ship path:** `wildfire_front/cn_wang_zhengfei.py` (`hybrid_ros_prior`), `scripts/run_cn_physics_prior.py`

---

## Summary

| Metric | Count |
|--------|------:|
| Vendor dirs (repos + assets) | 24+ |
| Pre-existing (before this goal wave) | 4 (CesiumFire, fire-spread, FireCellularAutomata, YongfengX-WildfireSpreadTS) |
| **New successful clones this wave** | **19** |
| New public data assets | 1 (FIRMS Europe 24h CSV) |
| Failed clones | 0 |
| Used by shipped WFD runtime | hybrid Wang/Mao math (reimplemented); rest = reference |

---

## Pre-existing `_vendor_cn` (before mega download)

| Path | Source | Use decision |
|------|--------|--------------|
| `fire-spread/` | xllyll/fire-spread | **Reference** polar 360° + 王正非 README → inspired `hybrid_ros_prior` / polar envelope |
| `CesiumFire/` | winrelde/CesiumFire | **Vendor-only** Vue/Cesium UI — no ship |
| `FireCellularAutomata/` | Samyak-Surti | **Reference** CA → inspired `cn_cellular_ca.py` |
| `YongfengX-WildfireSpreadTS/` | YongfengX | **Research only** ML next-day (G1 KILL) |

---

## New downloads (this goal)

| Path | Upstream | License note | Use / no-use |
|------|----------|--------------|--------------|
| `ForestFireSpreadBackEnd/` | winrelde/ForestFireSpreadBackEnd | See repo; data stripped | **Vendor-only** Java API pattern |
| `Jishnu-FOREST_FIRE-CA/` | Jishnuadhikary10/FOREST_FIRE-USING-CELLULAR-AUTOMATA | See repo | **Reference** probabilistic CA + wind |
| `xaquaaa-forest_fire/` | xaquaaa/forest_fire | See repo | **Reference** UNet/LSTM/CA stack |
| `brian-xu-wildfire-prediction/` | brian-xu/wildfire-prediction | See repo | **Research** DL spread (archived) |
| `bronteee-fire-asufm/` | bronteee/fire-asufm | See repo | **Research** ASUFM paper code |
| `aryan-ORS-project/` | aryan-agrawal7/ORS-project | See repo | **Reference** ML-CA GIS |
| `Jaideep193-forest-fire-detection/` | Jaideep193/forest-fire-detection | See repo | **Reference** VIIRS + RF + CA India |
| `issam-njh-ca-spread/` | issam-njh/…cellular-automata | See repo | **Reference** CA spread paper impl |
| `cell2fire/` | cell2fire/Cell2Fire | See repo | **Compare later** CA ops simulator (needs build) |
| `forefire/` | forefireAPI/forefire | JOSS / open | **Compare later** physics ROS (C++) |
| `elmfire/` | lautenberger/elmfire | See repo | **Compare later** level-set ops US |
| `WildFireSpread-nikos/` | nikos230/WildFireSpread | See repo | **Research** BA DL thesis |
| `fs_demo-lishulin/` | lishulincug/fs_demo | See repo | **Vendor-only** 森林防火 Baidu Map UI |
| `smart-forest-farm/` | fumu-keji/smart-forest-farm | See repo | **Vendor-only** 智慧林场 dashboard |
| `ForestFireSpreadSystem/` | icydengyw/… | See repo | **Empty** README-only note |
| `Junction-Asia-Deflare/` | Junction-Asia-2025-Deflare/… | See repo | **Research** multi-kernel CNN |
| `AyushZero-TrialByFire/` | AyushZero/TrialByFire-… | See repo | **Research** LSTM+physics VIIRS |
| `pignode-wildfire/` | josephyu12/pignode-wildfire | See repo | **Research** PINN GNN ODE |
| `fire-spread-xllyll-README-only-check/` | xllyll/fire-spread (re-clone) | See repo | **Dup of fire-spread/** for completeness |
| `_assets/J1_VIIRS_C2_Europe_24h_sample.csv` | NASA FIRMS public | Public domain / NASA | **Usable** hotspot overlay sample (~180 KB) |

---

## Shipped project wiring (not vendor runtime)

| Component | Role |
|-----------|------|
| `wildfire_front/cn_wang_zhengfei.py` | Wang/Mao + **`hybrid_ros_prior`** (obs magnitude × physics shape) + GeoJSON polar |
| `wildfire_front/cn_cellular_ca.py` | Minimal CA demo |
| `wildfire_front/emergency_products.py` | `enrich_ops_dict(..., cn_hybrid=True)` attaches summary |
| `scripts/run_cn_physics_prior.py` | CLI entry Tobarra-like default 5.71 m/min |
| `tests/test_cn_wang_zhengfei.py` | Unit + hybrid + CLI |
| `tests/test_emergency_products.py` | Asserts `cn_hybrid_ros` on enrich |
| `docs/MEGA_ANALISIS_CHINA_LINHUO.md` | Technical mega-analysis |

### CLI

```bash
python scripts/run_cn_physics_prior.py --obs-ros 5.71 --geojson-origin 500000,4300000
python -m pytest tests/test_cn_wang_zhengfei.py tests/test_emergency_products.py -q
```

---

## Failures / honesty notes

- All listed clone URLs **succeeded** in this environment (exit 0).  
- Empty repos (e.g. ForestFireSpreadSystem) still count as **downloaded with note: no usable source**.  
- Large simulators (Cell2Fire, ForeFire, ELMFIRE) are **downloaded for offline study** — not built/run as part of CI.  
- No proprietary Chinese emergency APIs or private DEMs were accessed.  
- `_vendor_cn/` is **local cache**; do not force-push multi-GB trees to origin.

---

## How to re-download

```powershell
# See implementer log for exact URL list; or re-run shallow clones into _vendor_cn/
git clone --depth 1 <url> _vendor_cn/<name>
```
