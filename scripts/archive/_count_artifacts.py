from pathlib import Path

A = Path("artifacts")
fires = [
    "cardoso_2025",
    "la_estrella_acom1_2024",
    "la_estrella_acom2_2024",
    "hellin_2024",
    "retuerta_2025",
    "brazatortas_2025",
    "polan_2025",
]
for f in fires:
    tifs = list((A / f"{f}_reprojected_lwir").glob("*.tif"))
    masks = list((A / f"{f}_lwir_masks").glob("*_mask.tif"))
    print(f"{f:28s} TIFs={len(tifs):4d}  masks={len(masks):4d}")
