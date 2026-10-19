# Private real-incident files (not redistributed)

Some third-party thermal and perimeter products were used locally for the
Tobarra fire (2024-08-02). Permission covers reporting that use. It does not
cover committing or redistributing the files.

Place a local copy here (this directory's contents are gitignored):

```
data/real_if/private/tobarra_20240802_perimeters/
```

Or point `WFD_PRIVATE_TOBARRA_PERIMETERS` at any directory outside the tree.

Scripts and tests that need those files skip when the directory is missing.
They do not fail the suite. Expected names, if you have a local copy:

- `2024020124_TOBARRA_20240802_1830.kmz` (or `.kml`)
- `2024020124_TOBARRA_20240802_2143.kmz` (or `.kml`)
- `inventory.json` (optional; area checks fall back to built-in expectations)

Do not commit KMZ, KML, GeoJSON, imagery, or inventory bytes from this drop.
