# Canadian Fire Spread Dataset (CFSDS)

- Pack id: `cfsds`
- License: `cc-by-4.0` (research proxy; paper 10.1038/s41597-024-03436-4)
- OSF DOI: `10.17605/OSF.IO/F48RY`
- URL: https://osf.io/f48ry/
- Downloaded files: 26 · bytes 62726634
- Used 2023 groups: 21717 rows · 621 fire IDs · 593 IDs with ≥3 daily rows
- Author `sprdistm` / `firearea` unused (not product ROS/ha)

## Use in WildfireFrontDynamics

- Lab / research open data only.
- Decision support ≠ tactical dispatch.
- CFSDS ≠ official ES cadastre / O2.
- Daily growth / DOY rasters are author interpolation, not product ROS.
- GeoTIFF R1 contract skipped (no ≥3 aligned incident scenes).

## Non-claims

- Not field_ops GO from this pack.
- Not official burned-area cadastre.
- Not invented IoU/ROS.

Inventory schema: `wfd_external_ros_inventory_v1`
