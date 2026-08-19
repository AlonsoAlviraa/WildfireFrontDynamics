"""Cinematic 1080p frames: how to read the sala de mando.

Teaching film for a command-post viewer. Spanish meaning first, real SPA
shots with callouts. Does not invent GO_Q or dispatch. CLI stays out.
"""

from __future__ import annotations

import json
import subprocess
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SIZE = (1920, 1080)
BG = (11, 18, 32)
PANEL = (17, 24, 39)
LINE = (31, 41, 55)
TEXT = (249, 250, 251)
MUTED = (156, 163, 175)
FAINT = (107, 114, 128)
CYAN = (14, 165, 233)
LOCAL = (56, 189, 248)
GO = (34, 197, 94)
HOLD = (245, 158, 11)
ABSTAIN = (239, 68, 68)

WORD = {
    "GO": "SEGUIR",
    "HOLD": "ESPERAR",
    "ABSTAIN": "SE CALLA",
    "BRIEF": "SIN TARJETA",
}
SHORT = {
    "GO": "El sistema propone seguir con esta lectura. No es una orden.",
    "HOLD": "Espera: los datos no bastan o chocan.",
    "ABSTAIN": "El sistema se calla a propósito. Callarse no es un fallo.",
    "BRIEF": "Sin tarjeta de este incendio.",
}
CHAPTER_ES = {
    "cli_commands": "Mapa de la consola",
    "cli_flags": "Banderas de honestidad",
    "cli_catalog": "Catálogo de lab — no es campo",
    "cli_policies": "Políticas de decisión",
    "fire_doctor": "Doctor del incendio",
    "fire_status": "Estado del incendio",
    "fire_decide": "Decidir — field_ops",
    "cli_card": "Tarjeta de decisión",
    "cli_snapshot": "Congelar este momento",
    "cli_compare": "Qué cambió",
    "cli_export_acta": "Acta de auditoría",
    "cli_replay": "Replay forense",
    "cli_operator": "Hub del operador",
    "app_list": "Incendios en consola",
    "app_build": "Sala de mando",
}
SURFACE_ES = {"cli": "CONSOLA", "app": "SALA DE MANDO", "fire_e2e": "INCENDIO"}
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
WIN_FONTS = Path(r"C:\Windows\Fonts")
TITLE_BG_CANDIDATES = (
    Path("outputs/walkthrough/assets/title_bg.jpg"),
    Path("outputs/walkthrough/assets/end_bg.jpg"),
)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = WIN_FONTS / name
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def fonts() -> dict[str, ImageFont.ImageFont]:
    return {
        "hero": _font("segoeuib.ttf", 92),
        "h1": _font("segoeuib.ttf", 54),
        "h2": _font("segoeuib.ttf", 36),
        "h3": _font("segoeui.ttf", 26),
        "body": _font("segoeui.ttf", 22),
        "small": _font("segoeui.ttf", 18),
        "micro": _font("segoeui.ttf", 15),
        "mono": _font("consola.ttf", 20),
        "mono_sm": _font("consola.ttf", 16),
        "badge": _font("segoeuib.ttf", 16),
    }


def _load_bg(path: Path | None, size: tuple[int, int] = SIZE) -> Image.Image:
    w, h = size
    if path and path.is_file():
        im = Image.open(path).convert("RGB")
        im = ImageEnhance.Brightness(im).enhance(0.55)
        im = ImageEnhance.Contrast(im).enhance(1.15)
        im = im.resize(size, Image.Resampling.LANCZOS)
        return im
    img = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(img, "RGBA")
    for i in range(0, w, 48):
        draw.line((i, 0, i, h), fill=(30, 58, 90, 40))
    for j in range(0, h, 48):
        draw.line((0, j, w, j), fill=(30, 58, 90, 40))
    draw.rectangle((0, 0, w, h), fill=(11, 18, 32, 90))
    return img


def _round(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, r: int = 14) -> None:
    draw.rounded_rectangle(box, radius=r, fill=fill)


def _badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill, fnt) -> None:
    x, y = xy
    pad_x, pad_y = 14, 7
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    _round(draw, (x, y, x + tw + pad_x * 2, y + th + pad_y * 2), fill, 8)
    draw.text((x + pad_x, y + pad_y - 1), text, fill=BG, font=fnt)


def _progress(draw: ImageDraw.ImageDraw, index: int, total: int, y: int = 24) -> None:
    w, _ = SIZE
    x0, x1 = 80, w - 80
    draw.rounded_rectangle((x0, y, x1, y + 4), radius=2, fill=LINE)
    if total <= 0:
        return
    frac = max(0.04, min(1.0, index / total))
    draw.rounded_rectangle((x0, y, x0 + int((x1 - x0) * frac), y + 4), radius=2, fill=CYAN)


def _footer(draw: ImageDraw.ImageDraw, fnt) -> None:
    w, h = SIZE
    draw.rectangle((0, h - 64, w, h), fill=(8, 12, 22))
    draw.line((0, h - 64, w, h - 64), fill=LINE)
    draw.text(
        (80, h - 42),
        "Apoyo a la decisión  ·  no es orden de despacho  ·  GO_Q partial  ·  fusion ON ≠ despacho",
        fill=MUTED,
        font=fnt,
    )


def _parse(stdout: str) -> Any:
    blob = (stdout or "").strip()
    if not blob:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        start, end = blob.find("{"), blob.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(blob[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, float):
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"
    return str(v)


def mando_decision(row: dict[str, Any]) -> str | None:
    raw = row.get("decision")
    if raw in WORD:
        return str(raw)
    data = _parse(row.get("stdout") or "")
    if isinstance(data, dict):
        for key in ("decision",):
            if data.get(key) in WORD:
                return str(data[key])
        for nest in ("summary", "result", "card"):
            inner = data.get(nest)
            if isinstance(inner, dict) and inner.get("decision") in WORD:
                return str(inner["decision"])
    return None


def pretty_facts(row: dict[str, Any]) -> list[tuple[str, str]]:
    """Mando-readable key/values from a real chapter stdout. Never invents ROS."""
    data = _parse(row.get("stdout") or "")
    cid = str(row.get("id") or "")
    out: list[tuple[str, str]] = []
    if not isinstance(data, dict):
        rc = row.get("returncode")
        out.append(("salida", "ok" if rc == 0 else f"exit {rc}"))
        return out

    def add(label: str, value: Any) -> None:
        if value is None or value == "":
            return
        out.append((label, _fmt(value)))

    if cid == "cli_flags":
        add("GO_Q", data.get("GO_Q") or data.get("go_q") or "partial")
        add("fusión field_ops", data.get("field_ops_fusion") or data.get("field_ops_ml_live_fusion"))
        add("no despacho", data.get("not_tactical_dispatch"))
        return out[:6]
    if cid == "cli_catalog":
        products = data.get("products") or data.get("items") or []
        add("productos", len(products) if isinstance(products, list) else products)
        add("nota", "holdout de lab · no es score de campo")
        return out[:6]
    if cid == "cli_commands":
        groups = data.get("groups") or []
        add("grupos", len(groups) if isinstance(groups, list) else None)
        add("entrada", "python -m wildfire_front")
        return out[:6]
    if cid == "cli_policies":
        pols = data.get("policies") or data.get("items") or []
        add("políticas", len(pols) if isinstance(pols, list) else None)
        add("campo", "field_ops")
        return out[:6]
    if cid == "fire_status":
        m = data.get("metrics") or data.get("ops") or data
        add("calidad", m.get("quality_grade") if isinstance(m, dict) else None)
        if isinstance(m, dict):
            add("velocidad citada", m.get("primary_ros_m_min") or m.get("speed_median_m_min"))
            add("área ha", m.get("area_ha_max") or m.get("area_ha_last"))
            add("fotos", m.get("n_frames") or m.get("num_observations"))
        return out[:6]
    if cid == "fire_doctor":
        add("doctor", "ok" if data.get("ok") is not False else "revisar")
        issues = data.get("issues") or data.get("errors") or []
        add("avisos", len(issues) if isinstance(issues, list) else issues)
        return out[:6]
    if cid in {"fire_decide", "cli_card"}:
        card = data.get("result") or data.get("summary") or data
        if not isinstance(card, dict):
            card = data
        add("lectura", WORD.get(str(card.get("decision") or "").upper(), card.get("decision")))
        conf = card.get("confidence_pred")
        if isinstance(conf, (int, float)):
            add("calidad lectura", f"{round(conf * 100)}% · no es ROS")
        add("incendio", card.get("event_id"))
        srcs = card.get("sources") or []
        if isinstance(srcs, list) and srcs:
            miss = [s.get("id") for s in srcs if isinstance(s, dict) and s.get("available") is False]
            add("fuentes", "incompletas" if miss else "presentes")
            if miss:
                add("falta", ", ".join(str(x) for x in miss[:3]))
        return out[:7]
    if cid == "cli_snapshot":
        cited = data.get("cited") or {}
        add("ROS citado", cited.get("ros_m_min") if isinstance(cited, dict) else None)
        add("área ha", cited.get("area_ha") if isinstance(cited, dict) else None)
        add("calidad", cited.get("quality_grade") if isinstance(cited, dict) else None)
        add("inventado", "no" if isinstance(cited, dict) and cited.get("invented") is False else None)
        add("despacho", "no")
        return out[:6]
    if cid == "cli_compare":
        add("cambio", "sí" if data.get("flipped") else "sin flip")
        add("de → a", f"{data.get('from') or '—'} → {data.get('to') or '—'}")
        delta = data.get("cited_delta") or {}
        if isinstance(delta, dict):
            add("Δ ROS", delta.get("ros_m_min"))
            add("Δ ha", delta.get("area_ha"))
        add("alerta", "local · no SMS")
        return out[:6]
    if cid == "cli_export_acta":
        s = data.get("summary") or data
        if isinstance(s, dict):
            add("acta", Path(str(s.get("acta") or s.get("path") or "outbox")).name)
            add("decisión", s.get("decision"))
        add("tipo", "forense · no es acta H1")
        return out[:6]
    if cid == "cli_replay":
        s = data.get("summary") or data
        if isinstance(s, dict):
            add("replay_ok", s.get("replay_ok"))
            add("esperado", s.get("expected"))
            add("obtenido", s.get("got"))
        add("nota", "consistencia · no crypto")
        return out[:6]
    if cid == "cli_operator":
        add("GO_Q", data.get("GO_Q") or (data.get("rails") or {}).get("GO_Q") or "partial")
        add("hub", "operator")
        return out[:6]
    if cid == "app_list":
        fires = data.get("fires") or data.get("items") or []
        add("incendios", len(fires) if isinstance(fires, list) else None)
        add("modo", "Fácil")
        return out[:6]
    if cid == "app_build":
        add("salida", "SPA mando")
        add("modo", "Fácil · SEGUIR / ESPERAR / SE CALLA")
        return out[:6]

    for key in ("decision", "GO_Q", "status", "ok"):
        if key in data:
            add(key, data.get(key))
    return out[:6]


def render_title(bg_path: Path | None = None) -> Image.Image:
    img = _load_bg(bg_path or next((p for p in TITLE_BG_CANDIDATES if p.is_file()), None))
    draw = ImageDraw.Draw(img, "RGBA")
    f = fonts()
    w, h = SIZE
    veil = Image.new("RGBA", SIZE, (8, 12, 22, 120))
    img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")
    draw = ImageDraw.Draw(img)
    _progress(draw, 0, 20)
    _badge(draw, (80, 80), "WFD  ·  SALA DE MANDO", CYAN, f["badge"])
    draw.text((80, 280), "WFD MANDO", fill=TEXT, font=f["hero"])
    draw.text((80, 400), "Cómo se lee la sala de mando.", fill=LOCAL, font=f["h2"])
    draw.text(
        (80, 470),
        "La palabra grande  ·  las cifras  ·  los tres botones  ·  meter fotos",
        fill=MUTED,
        font=f["body"],
    )
    _round(draw, (80, 560, 760, 628), (15, 23, 42))
    draw.text((104, 580), "No es orden de despacho   ·   GO_Q sigue partial", fill=HOLD, font=f["small"])
    _footer(draw, f["small"])
    return img


def render_section(label: str, kicker: str, *, index: int, total: int, bg_path: Path | None = None) -> Image.Image:
    img = _load_bg(bg_path or next((p for p in TITLE_BG_CANDIDATES if p.is_file()), None))
    veil = Image.new("RGBA", SIZE, (8, 12, 22, 150))
    img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 280), kicker, CYAN, f["badge"])
    draw.text((80, 360), label, fill=TEXT, font=f["hero"])
    _footer(draw, f["small"])
    return img


def _wrap_text(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw in str(text).splitlines() or [""]:
        line = ""
        for word in raw.split():
            trial = (line + " " + word).strip()
            if len(trial) > width:
                if line:
                    lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
    return lines or [""]


def render_lesson(
    title: str,
    body: str,
    *,
    kicker: str = "SALA DE MANDO",
    index: int = 1,
    total: int = 10,
    accent: tuple[int, int, int] = CYAN,
) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 72), kicker, accent, f["badge"])
    draw.text((80, 150), title, fill=TEXT, font=f["h1"])
    y = 260
    for line in _wrap_text(body, 46):
        draw.text((80, y), line, fill=MUTED, font=f["h3"])
        y += 46
        if y > 980:
            break
    _footer(draw, f["small"])
    return img


# Desktop C2: rail is --rail:min(420px, 40vw) → 420/1920 at 1080p.
SPA_REGIONS = {
    "full": (0.00, 0.00, 1.00, 1.00),
    "top": (0.00, 0.00, 1.00, 0.044),
    "map": (0.00, 0.044, 0.781, 1.00),
    "rail": (0.781, 0.044, 1.00, 1.00),
    "hero": (0.781, 0.044, 1.00, 0.267),
    "kpis": (0.781, 0.267, 1.00, 0.373),
    "need": (0.781, 0.373, 1.00, 0.546),
    "acts": (0.781, 0.546, 1.00, 0.650),
    "last": (0.781, 0.650, 1.00, 0.782),
    "tabs": (0.781, 0.782, 1.00, 1.00),
}


def render_spa_focus(
    shot: Image.Image,
    title: str,
    body: str,
    *,
    region: str = "full",
    index: int = 1,
    total: int = 10,
) -> Image.Image:
    """SPA crop on the right, explanation on the left."""
    canvas = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(canvas)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (64, 56), "EN PANTALLA", LOCAL, f["badge"])
    draw.text((64, 110), title, fill=TEXT, font=f["h2"])
    y = 180
    for line in _wrap_text(body, 28):
        draw.text((64, y), line, fill=MUTED, font=f["body"])
        y += 34
        if y > 980:
            break

    src = shot.convert("RGB")
    sw, sh = src.size
    boxes = {k: (int(a * sw), int(b * sh), int(c * sw), int(d * sh)) for k, (a, b, c, d) in SPA_REGIONS.items()}
    box = boxes.get(region, boxes["full"])
    crop = src.crop(box)
    frame = (820, 90, 1860, 990)
    _round(draw, frame, (8, 12, 22), 16)
    inner = (836, 106, 1844, 974)
    iw, ih = inner[2] - inner[0], inner[3] - inner[1]
    crop.thumbnail((iw, ih), Image.Resampling.LANCZOS)
    px = inner[0] + (iw - crop.size[0]) // 2
    py = inner[1] + (ih - crop.size[1]) // 2
    canvas.paste(crop, (px, py))
    _footer(draw, f["small"])
    return canvas


def render_three_words(*, index: int = 1, total: int = 10) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 56), "LA PALABRA GRANDE", CYAN, f["badge"])
    draw.text((80, 110), "Tres lecturas. Ninguna es una orden.", fill=TEXT, font=f["h2"])
    cards = (
        (GO, "SEGUIR", "GO", "El sistema propone seguir con esta lectura. Faltan fuentes: trátalo como espera. No lances medios por esta tarjeta."),
        (HOLD, "ESPERAR", "HOLD", "Los datos no bastan o chocan. Espera. Revisa qué falta antes de mover nada."),
        (ABSTAIN, "SE CALLA", "ABSTAIN", "El sistema se calla a propósito. Callarse no es un fallo. No inventa lo que no tiene."),
    )
    x = 80
    for color, word, code, body in cards:
        _round(draw, (x, 220, x + 560, 920), PANEL, 18)
        draw.rectangle((x, 220, x + 8, 920), fill=color)
        draw.text((x + 36, 260), word, fill=color, font=f["h1"])
        draw.text((x + 36, 340), code, fill=FAINT, font=f["mono"])
        y = 420
        for line in _wrap_text(body, 22):
            draw.text((x + 36, y), line, fill=MUTED, font=f["body"])
            y += 36
        x += 592
    _footer(draw, f["small"])
    return img


def render_spa_callout(
    shot: Image.Image,
    title: str,
    body: str,
    *,
    region: str = "full",
    index: int = 1,
    total: int = 10,
) -> Image.Image:
    """Full SPA with a spotlight on one zone and a caption on the dark map."""
    canvas = Image.new("RGB", SIZE, BG)
    src = shot.convert("RGB")
    area_h = SIZE[1] - 64
    fitted = src.copy()
    fitted.thumbnail((SIZE[0], area_h), Image.Resampling.LANCZOS)
    ox = (SIZE[0] - fitted.size[0]) // 2
    oy = (area_h - fitted.size[1]) // 2
    canvas.paste(fitted, (ox, oy))

    sx = fitted.size[0] / max(src.size[0], 1)
    sy = fitted.size[1] / max(src.size[1], 1)
    fx0, fy0, fx1, fy1 = SPA_REGIONS.get(region, SPA_REGIONS["full"])
    box = (
        ox + int(fx0 * src.size[0] * sx),
        oy + int(fy0 * src.size[1] * sy),
        ox + int(fx1 * src.size[0] * sx),
        oy + int(fy1 * src.size[1] * sy),
    )

    veil = Image.new("L", SIZE, 150)
    punch = ImageDraw.Draw(veil)
    punch.rounded_rectangle(box, radius=10, fill=0)
    dark = Image.new("RGBA", SIZE, (8, 12, 22, 150))
    dark.putalpha(veil)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), dark).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=10, outline=CYAN, width=3)

    f = fonts()
    _progress(draw, index, total)
    # Caption sits on the map when the rail is highlighted; otherwise lower-third.
    if region in {"hero", "kpis", "need", "acts", "last", "tabs", "rail"}:
        cap = (56, 120, 740, 780)
    else:
        cap = (64, 780, 1856, 1000)
    _round(draw, cap, (11, 18, 32), 16)
    draw.rectangle((cap[0], cap[1], cap[0] + 6, cap[3]), fill=CYAN)
    draw.text((cap[0] + 28, cap[1] + 20), title, fill=TEXT, font=f["h3"])
    y = cap[1] + 70
    wrap = 28 if (cap[2] - cap[0]) < 800 else 72
    for line in _wrap_text(body, wrap):
        draw.text((cap[0] + 28, y), line, fill=MUTED, font=f["body"])
        y += 32
        if y > cap[3] - 24:
            break
    _footer(draw, f["small"])
    return canvas


def render_cmd_card(title: str, cmd: str, note: str, *, index: int = 1, total: int = 4) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 80), "CÓMO SE ABRE", CYAN, f["badge"])
    draw.text((80, 160), title, fill=TEXT, font=f["h1"])
    _round(draw, (80, 280, 1840, 420), PANEL, 18)
    draw.text((112, 325), cmd, fill=LOCAL, font=f["h3"])
    draw.text((80, 470), note, fill=MUTED, font=f["body"])
    _footer(draw, f["small"])
    return img


def render_step_card(
    number: int,
    title: str,
    body: str,
    *,
    kicker: str = "METER FOTOS",
    index: int = 1,
    total: int = 4,
) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 80), kicker, HOLD, f["badge"])
    draw.text((80, 170), f"{number}.", fill=CYAN, font=f["hero"])
    draw.text((80, 300), title, fill=TEXT, font=f["h1"])
    # wrap body
    y = 400
    line = ""
    for word in body.split():
        trial = (line + " " + word).strip()
        if len(trial) > 52:
            draw.text((80, y), line, fill=MUTED, font=f["h3"])
            y += 48
            line = word
        else:
            line = trial
    if line:
        draw.text((80, y), line, fill=MUTED, font=f["h3"])
    _footer(draw, f["small"])
    return img


def render_end(bg_path: Path | None = None) -> Image.Image:
    img = _load_bg(bg_path or Path("outputs/walkthrough/assets/end_bg.jpg"))
    veil = Image.new("RGBA", SIZE, (8, 12, 22, 140))
    img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")
    draw = ImageDraw.Draw(img)
    f = fonts()
    _progress(draw, 1, 1)
    _badge(draw, (80, 160), "CIERRE", HOLD, f["badge"])
    draw.text((80, 230), "Listo para sala de mando", fill=TEXT, font=f["h1"])
    lines = [
        "1. Palabra grande: SEGUIR / ESPERAR / SE CALLA",
        "2. Qué hay · qué falta · qué hacer ahora",
        "3. Estado · Decidir · Acta   ·   Congelar · Qué cambió",
        "4. Meter fotos: carpeta → .tif → Procesar",
        "Fácil oculta ingeniería. GO_Q partial. No es despacho.",
    ]
    y = 340
    for line in lines:
        draw.text((80, y), line, fill=LOCAL if line.startswith("python") else MUTED, font=f["body"])
        y += 48
    _footer(draw, f["small"])
    return img


def render_chapter(row: dict[str, Any], *, index: int, total: int) -> Image.Image:
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    f = fonts()
    w, h = SIZE
    _progress(draw, index, total)
    surface = str(row.get("surface") or "cli")
    badge = SURFACE_ES.get(surface, surface.upper())
    color = {"cli": CYAN, "app": LOCAL, "fire_e2e": HOLD}.get(surface, CYAN)
    _badge(draw, (80, 56), badge, color, f["badge"])
    title = CHAPTER_ES.get(str(row.get("id") or ""), str(row.get("title") or ""))
    draw.text((80, 110), title, fill=TEXT, font=f["h1"])
    cmd = str(row.get("cmd") or "")
    draw.text((80, 184), cmd[:110], fill=FAINT, font=f["mono_sm"])

    dec = mando_decision(row)
    word = WORD.get(dec or "", "")
    word_col = {"GO": GO, "HOLD": HOLD, "ABSTAIN": ABSTAIN}.get(dec or "", CYAN)

    # Left facts panel
    _round(draw, (80, 240, 980, h - 100), PANEL, 18)
    facts = pretty_facts(row)
    y = 270
    draw.text((112, y), "Lectura del sistema", fill=MUTED, font=f["small"])
    y += 48
    if not facts:
        draw.text((112, y), "Sin resumen — comando ejecutado.", fill=TEXT, font=f["body"])
    for label, value in facts:
        draw.text((112, y), label.upper(), fill=FAINT, font=f["micro"])
        draw.text((112, y + 26), value[:48], fill=TEXT, font=f["h3"])
        y += 78
        if y > h - 180:
            break

    # Right decision / status plate
    _round(draw, (1020, 240, w - 80, h - 100), (15, 23, 42), 18)
    if word:
        draw.text((1060, 300), word, fill=word_col, font=f["hero"])
        if dec:
            draw.text((1064, 410), dec, fill=FAINT, font=f["mono"])
        draw.text((1060, 480), SHORT.get(dec or "", ""), fill=MUTED, font=f["body"])
        draw.text((1060, 560), "Orientación de card. No es despacho.", fill=HOLD, font=f["small"])
    else:
        rc = row.get("returncode")
        ok = rc == 0
        draw.text((1060, 320), "HECHO" if ok else "REVISAR", fill=GO if ok else ABSTAIN, font=f["h1"])
        draw.text((1060, 410), f"exit {rc}  ·  {row.get('elapsed_ms') or '—'} ms", fill=MUTED, font=f["mono"])
        draw.text((1060, 480), "Comando real  ·  python -m wildfire_front", fill=FAINT, font=f["small"])

    _footer(draw, f["small"])
    return img


def render_spa_plate(shot: Image.Image, *, caption: str, index: int, total: int) -> Image.Image:
    canvas = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(canvas)
    f = fonts()
    _progress(draw, index, total)
    _badge(draw, (80, 48), "SALA DE MANDO", LOCAL, f["badge"])
    draw.text((80, 96), caption, fill=TEXT, font=f["h2"])

    frame = (80, 170, 1840, 980)
    _round(draw, frame, (8, 12, 22), 16)
    inner = (96, 186, 1824, 964)
    iw, ih = inner[2] - inner[0], inner[3] - inner[1]
    src = shot.convert("RGB")
    src.thumbnail((iw, ih), Image.Resampling.LANCZOS)
    px = inner[0] + (iw - src.size[0]) // 2
    py = inner[1] + (ih - src.size[1]) // 2
    canvas.paste(src, (px, py))
    _footer(draw, f["small"])
    return canvas


def ken_burns(shot: Image.Image, n: int = 6) -> list[Image.Image]:
    """Slow push-in over a SPA screenshot."""
    src = shot.convert("RGB")
    w, h = SIZE
    base = src.resize((w, h), Image.Resampling.LANCZOS)
    frames: list[Image.Image] = []
    for i in range(n):
        t = i / max(n - 1, 1)
        scale = 1.0 + 0.08 * t
        nw, nh = int(w * scale), int(h * scale)
        grown = base.resize((nw, nh), Image.Resampling.LANCZOS)
        left = (nw - w) // 2
        top = int((nh - h) * 0.35)
        crop = grown.crop((left, top, left + w, top + h))
        frames.append(crop)
    return frames


def capture_spa_shots(html_dir: Path, dest_dir: Path, *, port: int = 8768) -> list[Path]:
    """Serve the built SPA and screenshot it in Chrome so the map can load tiles."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not (html_dir / "index.html").is_file():
        return []
    if not CHROME.is_file():
        return []

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(html_dir), **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)
    shots: list[Path] = []
    try:
        views = (
            ("spa_desktop.png", "http://127.0.0.1:{p}/index.html", 1920, 1080),
            ("spa_intake.png", "http://127.0.0.1:{p}/index.html?tab=newfire", 1920, 1080),
            ("spa_glossary.png", "http://127.0.0.1:{p}/index.html?tab=glossary", 1920, 1080),
            ("spa_wide.png", "http://127.0.0.1:{p}/index.html", 1600, 900),
        )
        for name, url_t, w, h in views:
            dest = dest_dir / name
            cmd = [
                str(CHROME),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--window-size={w},{h}",
                "--virtual-time-budget=8000",
                f"--screenshot={dest.resolve()}",
                url_t.format(p=port),
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            time.sleep(0.8)
            if dest.is_file() and dest.stat().st_size > 10_000:
                shots.append(dest)
    finally:
        server.shutdown()
    return shots


def write_cinema_frames(
    run: dict[str, Any],
    frames_dir: Path,
    *,
    spa_shots: list[Path] | None = None,
    title_bg: Path | None = None,
    end_bg: Path | None = None,
) -> tuple[list[Path], Path]:
    """Sala-de-mando lesson stills + ffmpeg concat. CLI chapters are not filmed."""
    del run  # run.json stays on disk; this cut does not narrate CLI/JSON.
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("frame_*.png"):
        old.unlink()
    seq: list[tuple[Path, float]] = []
    idx = 0
    total = 18

    def add(img: Image.Image, seconds: float) -> None:
        nonlocal idx
        dest = frames_dir / f"frame_{idx:04d}.png"
        img.save(dest, "PNG")
        seq.append((dest, seconds))
        idx += 1

    def _open(name: str) -> Image.Image | None:
        path = next((p for p in (spa_shots or []) if p.name == name), None)
        if path and path.is_file():
            try:
                return Image.open(path)
            except OSError:
                return None
        return None

    desk = _open("spa_desktop.png")
    intake = _open("spa_intake.png")
    gloss = _open("spa_glossary.png")

    add(render_title(title_bg), 4.2)
    add(
        render_lesson(
            "Así se lee esta pantalla",
            "Izquierda: el mapa. Derecha: la lectura.\n"
            "Primero la palabra grande. Luego las cifras.\n"
            "Luego qué hay, qué falta y qué hacer.\n"
            "Los botones van al final. No es una orden.",
            index=1,
            total=total,
        ),
        5.4,
    )
    if desk:
        add(
            render_spa_plate(
                desk,
                caption="Sala de mando  ·  mapa a la izquierda  ·  lectura a la derecha",
                index=1,
                total=total,
            ),
            4.6,
        )
        add(
            render_spa_callout(
                desk,
                "El mapa",
                "Cian = frente local, el que sale de vuestras fotos. Rosa = satélite FIRMS: un aviso, no el perímetro oficial. El botón de abajo a la derecha centra el incendio.",
                region="map",
                index=2,
                total=total,
            ),
            5.8,
        )
        add(
            render_spa_callout(
                desk,
                "Arriba: incendio y modo",
                "El desplegable elige el incendio. Fácil es el modo de sala. Pro enseña ingeniería: déjalo apagado en puesto.",
                region="top",
                index=2,
                total=total,
            ),
            5.0,
        )
    add(render_three_words(index=3, total=total), 6.4)
    add(
        render_lesson(
            "No es una orden de despacho",
            "La franja ámbar lo dice siempre: apoyo a la decisión.\n"
            "SEGUIR con fuentes a medias se trata como espera.\n"
            "GO_Q sigue partial. Fusion ON no es despacho.\n"
            "Nadie lanza medios por esta tarjeta.",
            index=4,
            total=total,
            accent=HOLD,
        ),
        5.6,
    )
    if desk:
        add(
            render_spa_callout(
                desk,
                "La palabra grande",
                "Aquí pone SEGUIR, ESPERAR o SE CALLA. Debajo, en gris, el código técnico (GO). La frase explica el matiz. La franja ámbar recuerda que no es despacho.",
                region="hero",
                index=4,
                total=total,
            ),
            6.2,
        )
        add(
            render_spa_focus(
                desk,
                "Calidad, no velocidad",
                "La barra y el 72 % miden si la lectura es fiable. No es la velocidad del frente. Confianza de tarjeta no es ROS.",
                region="hero",
                index=5,
                total=total,
            ),
            5.4,
        )
        add(
            render_spa_callout(
                desk,
                "Las cuatro cifras",
                "Velocidad citada, área citada, calidad de las fotos y tiempo entre fotos. Solo salen si hay cita. Si no hay dato, sale una raya. Nunca se inventa.",
                region="kpis",
                index=5,
                total=total,
            ),
            6.0,
        )
        add(
            render_spa_callout(
                desk,
                "Qué hay · qué falta · qué hacer",
                "Esta caja manda. Qué hay: fotos y cifras. Qué falta: aquí, el perímetro de Copernicus. Qué hacer ahora: hay lectura, pero trátalo como espera. No lances medios.",
                region="need",
                index=6,
                total=total,
            ),
            6.6,
        )
        add(
            render_spa_focus(
                desk,
                "Lee esto antes de pulsar",
                "Si falta el satélite oficial, la acción es esperar aunque la palabra diga SEGUIR. La caja azul es la consigna del puesto.",
                region="need",
                index=6,
                total=total,
            ),
            5.2,
        )
        add(
            render_spa_callout(
                desk,
                "Tres botones de trabajo",
                "Estado = qué hay ahora. Decidir = leer la tarjeta. Acta = guardar la auditoría. El del medio es el de cada ronda.",
                region="acts",
                index=7,
                total=total,
            ),
            5.8,
        )
        add(
            render_spa_focus(
                desk,
                "Congelar y comparar",
                "Congelar guarda este instante. Qué cambió avisa en pantalla si la lectura da la vuelta. Es alerta local. No es SMS ni despacho.",
                region="acts",
                index=7,
                total=total,
            ),
            5.4,
        )
        add(
            render_spa_callout(
                desk,
                "Las pestañas de abajo",
                "Decisión enseña la tarjeta. Resumen, las cifras. Qué hacer, la lista. Meter fotos, las imágenes. Términos, el diccionario del puesto.",
                region="tabs",
                index=8,
                total=total,
            ),
            5.4,
        )
    add(render_section("Meter fotos", "EN LA MISMA PANTALLA", index=9, total=total, bg_path=title_bg), 2.0)
    add(
        render_step_card(
            1,
            "Abre la carpeta",
            "Un botón abre el Explorador de Windows. Ahí van las fotos del incendio. No hace falta terminal.",
            index=9,
            total=total,
        ),
        4.0,
    )
    add(
        render_step_card(
            2,
            "Suelta las fotos térmicas",
            "Solo .tif con mapa y fecha en el nombre, por ejemplo 20260817_153000_frente.tif. Un JPG del móvil no sirve.",
            index=10,
            total=total,
        ),
        5.0,
    )
    add(
        render_step_card(
            3,
            "Pulsa Procesar",
            "El sistema lee las fotos y actualiza la palabra grande. Si faltan datos, se calla. Eso es correcto.",
            index=11,
            total=total,
        ),
        4.4,
    )
    if intake:
        add(
            render_spa_plate(
                intake,
                caption="Pestaña Meter fotos  ·  tres pasos  ·  sin consola",
                index=11,
                total=total,
            ),
            5.2,
        )
        add(
            render_spa_focus(
                intake,
                "Nombre, carpeta, Procesar",
                "Pon el nombre del incendio. Abre la carpeta o suelta los .tif. Pulsa Procesar. El JPG se rechaza en castellano.",
                region="tabs",
                index=12,
                total=total,
            ),
            5.4,
        )
    if gloss:
        add(
            render_spa_plate(
                gloss,
                caption="Términos  ·  el diccionario de la sala",
                index=13,
                total=total,
            ),
            4.2,
        )
    add(
        render_lesson(
            "Fácil en puesto. Pro solo si hace falta.",
            "Fácil oculta bitácora, V&V y ensayo H1.\n"
            "Pro es para quien monta el sistema.\n"
            "En sala de mando se trabaja en Fácil.\n"
            "La interrogación de arriba abre esta misma guía.",
            index=14,
            total=total,
        ),
        5.2,
    )
    add(render_end(end_bg), 5.0)

    concat = frames_dir / "concat.txt"
    lines = []
    for path, seconds in seq:
        posix = path.resolve().as_posix()
        lines.append(f"file '{posix}'")
        lines.append(f"duration {seconds:.2f}")
    if seq:
        lines.append(f"file '{seq[-1][0].resolve().as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [p for p, _ in seq], concat


def encode_concat(concat: Path, dest: Path, *, crf: int = 18) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p,fade=t=in:st=0:d=0.6",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        str(crf),
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[-3000:],
        "path": str(dest),
        "bytes": dest.stat().st_size if dest.is_file() else 0,
    }
