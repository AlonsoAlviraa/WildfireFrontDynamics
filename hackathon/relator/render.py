"""One-page source board for the demo video. Not the product SPA."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .board import CELL_IDS


def _cell_html(cid: str, cell: dict[str, Any]) -> str:
    st = escape(str(cell.get("status") or "missing"))
    val = cell.get("value")
    cite = cell.get("cite")
    note = escape(str(cell.get("note") or ""))
    extra = f"<strong>{escape(str(val))}</strong> " if val is not None else ""
    cite_h = f'<span class="cite">cite:{escape(str(cite))}</span>' if cite else ""
    return (
        f'<div class="cell {st}"><div class="id">{escape(cid)}</div>'
        f'<div class="st">{st}</div><div class="v">{extra}{cite_h}</div>'
        f'<p>{note}</p></div>'
    )


def _chip_html(chip: dict[str, Any]) -> str:
    path = Path(str(chip.get("path") or ""))
    src = str(chip.get("url") or "")
    if not src and path.is_file():
        import base64

        src = "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    cap = escape(f"{chip.get('sensor') or 'sat'} · {chip.get('role')} · {chip.get('date')}")
    cite = escape(str(chip.get("cite") or ""))
    img = f'<img src="{src}" alt="{cap}"/>' if src else f'<div class="missing-chip">{cap}</div>'
    return f'<figure>{img}<figcaption>{cap}<br/><span class="cite">{cite}</span></figcaption></figure>'


def frame_html(board: dict[str, Any], *, idx: int) -> str:
    cells = board.get("cells") or {}
    grid = "".join(_cell_html(cid, cells.get(cid) or {}) for cid in CELL_IDS)
    place = escape(str((board.get("place") or {}).get("label") or "—"))
    dec = escape(str(board.get("decision") or "ABSTAIN"))
    reason = escape(str(board.get("decision_reason") or ""))
    brief = escape(str(board.get("briefing") or ""))
    struck = (board.get("fiscal") or {}).get("struck") or []
    fiscal = "FISCAL OK" if not struck else f"FISCAL STRUCK {len(struck)}"
    sky = board.get("sky") or {}
    chips = "".join(_chip_html(c) for c in (sky.get("chips") or [])[:6])
    look = escape(str((sky.get("look") or {}).get("text") or ""))
    sky_block = (
        f'<div class="sky">{chips}</div><p class="look">{look}</p>' if chips or look else ""
    )
    return (
        f'<section class="frame"><h2>T+{idx} · {dec}</h2>'
        f'<p class="place">{place}</p><div class="grid">{grid}</div>'
        f"{sky_block}"
        f'<p class="reason">{reason}</p>'
        f'<p class="brief">{brief}</p>'
        f'<p class="fiscal">{escape(fiscal)}</p></section>'
    )


def page(frames: list[dict[str, Any]]) -> str:
    body = "".join(frame_html(b, idx=i) for i, b in enumerate(frames))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Relator — source board (not dispatch)</title>
<style>
body{{font:16px/1.4 ui-sans-serif,system-ui;background:#111;color:#eee;margin:24px}}
h1,h2{{font-weight:600}}
.rail{{border:1px solid #c45;color:#f8c;padding:8px 12px;margin-bottom:16px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}
.cell{{border:1px solid #333;padding:8px}}
.cell.missing{{opacity:.5}}
.cell.present{{border-color:#7af}}
.cell.cited{{border-color:#6c6}}
.cell.struck{{border-color:#c45;background:#311}}
.cite{{color:#9c9}}
.frame{{margin:24px 0;padding:16px;border-top:1px solid #333}}
.fiscal{{letter-spacing:.04em}}
.sky{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin:12px 0}}
.sky img{{width:100%;height:auto;border:1px solid #333;background:#000}}
.sky figcaption{{font-size:12px;color:#bbb}}
.look{{color:#cde}}
</style></head><body>
<h1>Relator · constellation desk</h1>
<p class="rail">VIIRS / Sentinel-2 chips are the evidence. The sealed decide() judges. No language model.
Not tactical dispatch. GO_Q partial. Thermal anomalies ≠ official burned area.</p>
{body}
</body></html>
"""


def write_html(frames: list[dict[str, Any]], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(frames), encoding="utf-8")
    return path
