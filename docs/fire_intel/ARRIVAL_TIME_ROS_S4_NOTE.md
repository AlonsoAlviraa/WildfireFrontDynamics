# Arrival-time ROS (deep research S4)

**UTC:** 2026-08-05T11:33:49.285470+00:00
**Status:** **OK**

## Method (literature + WFD)

- O'Neill et al. (IJWF 2024): arrival-time raster → **ROS = 60 / |∇T| m/min** (geometry, not IoU).
- Lampman et al. (IJWF 2026): multi-pass TIR method anchor — **not** Tobarra SLA.
- WFD: `wildfire_front/geometry_speed.py` + `arrival_ros.py` + `reconstruct_arrival_from_components` + multipass runner.

## Multi-pass discovery

- On-disk paired frames: **35**
- Window: `2024-08-02T16:08:21.553Z` → `2024-08-02T18:11:11.534Z`
- Multipass export status: **OK**
- Primary ROS: `6.135704762450378` m/min
- O'Neill median: `1.2796073951222064` m/min

## On-disk inventory (this run)

- Artifact hits scanned: **9**
- `outputs/tobarra_multipass_s4/arrival_field_stats.json` status=None keys=['oneill_ros']
- `outputs/tobarra_multipass_s4/front_dynamics_s4.json` status=None keys=['primary_methods_used', 'primary_ros_m_min', 'primary_ros_n', 'primary_ros_p25_m_min', 'primary_ros_p75_m_min']
- `outputs/tobarra_multipass_s4/s4_board.json` status=OK keys=['arrival_oneill_ros', 'geometry_ros', 'hybrid_refs', 'status']
- `outputs/tobarra_multipass_s4/operational_s4.json` status=None keys=['primary_ros_m_min', 'reference_vp_m_min', 'speed_defendable', 'speed_median_m_min', 'speed_vs_ref_grade', 'speed_vs_ref_ratio']
- `outputs/incidents/_sla_measure/outbox/front_dynamics.json` status=None keys=['geometry_speed', 'primary_methods_used', 'primary_ros_m_min', 'primary_ros_n', 'primary_ros_p25_m_min', 'primary_ros_p75_m_min', 'ros_area', 'ros_equiv_radius', 'ros_normal']
- `outputs/incidents/_sla_measure/outbox/operational_metrics.json` status=None keys=['arrival_cells_observed', 'arrival_resolution_m', 'cn_hybrid_ros', 'max_plausible_speed_m_min', 'num_speed_estimates', 'primary_methods_used', 'sector_ros', 'speed_abstention_reasons', 'speed_defendable', 'speed_iqr_m_min', 'speed_mean_m_min', 'speed_median_m_min', 'speed_n_implausible_filtered', 'speed_n_observable', 'speed_n_raw_observable', 'speed_p25_m_min', 'speed_p75_m_min', 'speed_p95_m_min', 'speed_status', 'speed_uncertainty_median_m_min']
- `outputs/gold_e2e/tobarra_work/outbox/operational_metrics.json` status=None keys=['arrival_cells_observed', 'arrival_resolution_m', 'max_plausible_speed_m_min', 'num_speed_estimates', 'primary_methods_used', 'reference_vp_m_min', 'sector_ros', 'sector_ros_source', 'speed_abstention_reasons', 'speed_defendable', 'speed_iqr_m_min', 'speed_mean_m_min', 'speed_median_m_min', 'speed_n_implausible_filtered', 'speed_n_observable', 'speed_n_raw_observable', 'speed_p25_m_min', 'speed_p75_m_min', 'speed_p95_m_min', 'speed_status', 'speed_uncertainty_median_m_min', 'speed_vs_ref_grade', 'speed_vs_ref_interpretation_es', 'speed_vs_ref_ratio']
- `outputs/observatorio/tobarra_20240802/front_dynamics.json` status=None keys=['geometry_speed', 'primary_methods_used', 'primary_ros_m_min', 'primary_ros_n', 'primary_ros_p25_m_min', 'primary_ros_p75_m_min', 'ros_area', 'ros_equiv_radius', 'ros_normal']
- `outputs/observatorio/tobarra_20240802/operational_metrics.json` status=None keys=['arrival_cells_observed', 'arrival_resolution_m', 'max_plausible_speed_m_min', 'num_speed_estimates', 'primary_methods_used', 'reference_vp_m_min', 'sector_ros', 'speed_abstention_reasons', 'speed_defendable', 'speed_iqr_m_min', 'speed_mean_m_min', 'speed_median_m_min', 'speed_n_implausible_filtered', 'speed_n_observable', 'speed_n_raw_observable', 'speed_p25_m_min', 'speed_p75_m_min', 'speed_p95_m_min', 'speed_status', 'speed_uncertainty_median_m_min', 'speed_vs_ref_grade', 'speed_vs_ref_interpretation_es', 'speed_vs_ref_ratio']

## Kill / success

| | |
|--|--|
| Success | Multi-frame export → arrival + ROS vs Vp table |
| Kill / blocked | Single frame or coreg fail → document BLOCKED |

## Rails

- ml_product_go false · fusion OFF · IoU ≠ ROS

Machine: `C:/Users/Mariano/Documents/ALONSOO/WildfireFrontDynamics/outputs/ml_eval/lab_loop/deep_research_s4_arrival_ros.json`
Runner: `python scripts/run_tobarra_multipass_s4.py`
