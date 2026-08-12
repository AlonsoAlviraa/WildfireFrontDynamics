"""
Send personalized IF-completo outreach emails via Gmail API.
Uses ~/.gmail-mcp OAuth. Dry-run with --dry-run. Log to docs/.
"""

from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "docs" / f"_outreach_send_log_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
CRED_PATH = Path.home() / ".gmail-mcp" / "credentials.json"
OAUTH_PATH = Path.home() / ".gmail-mcp" / "gcp-oauth.keys.json"

SIGNATURE_ES = """\
Alonso Alvira Ballano
Proyecto propio — dinámica de frente / apoyo a la decisión en incendios
alonso.alvbal@gmail.com
"""

SIGNATURE_PT = """\
Alonso Alvira Ballano
Projeto próprio — dinâmica de frente / apoio à decisão em incêndios
alonso.alvbal@gmail.com
"""

SIGNATURE_EN = """\
Alonso Alvira Ballano
Independent project — fire-front dynamics / decision support
alonso.alvbal@gmail.com
"""

# --- Shared "complete fire package" blocks ---------------------------------

PACK_ES = """\
QUÉ ENTENDEMOS POR «INCENDIO COMPLETO» (paquete ideal; cualquier
subconjunto liberable ya es muy útil):

A) GEOMETRÍA
   • Perímetro vectorial final (SHP / GPKG / GeoJSON / KMZ).
   • Si existe: secuencia multi-hora o multi-día del mismo incendio
     (perímetros activos o monitores sucesivos).
   • CRS y fecha/hora de cada geometría.

B) ANCLA OPERATIVA (para validar ROS; no inventamos cifras)
   • Superficie (ha) de parte o boletín.
   • Velocidad de propagación o ROS medio (m/min o m/h) si está en parte.
   • Fecha y hora del parte / fuente (UNAP, parte regional, etc.).

C) CRONOLOGÍA
   • Detección, ataque, control, extinción (aunque sea aproximada).

D) SI EXISTE (no bloquea si no hay)
   • Secuencia térmica / LWIR o RGB-T multi-pasada con timestamps y CRS.
   • Metadatos de sensor (plataforma, GSD, altitud, banda).
   • Meteorología local (viento dir/vel, T, HR) en la ventana del IF.
   • Combustible / modelo de vegetación del sector.

E) CONDICIONES DE USO
   • Uso interno del proyecto, sin redistribuir crudos sin acuerdo.
   • Puedo firmar nota de uso o NDA breve si lo requieren.

No necesitamos "todo el archivo histórico": con 1–3 incendios bien documentados
basta. Preferimos un incendio COMPLETO a muchos parciales.
"""

PACK_PT = """\
O QUE ENTENDEMOS POR «FOGO COMPLETO» (pacote ideal; qualquer subconjunto
libertável já é muito útil):

A) GEOMETRIA
   • Perímetro vetorial final (SHP / GPKG / GeoJSON / KMZ).
   • Se existir: sequência multi-hora ou multi-dia do mesmo fogo.
   • CRS e data/hora de cada geometria.

B) ÂNCORA OPERACIONAL (para validar ROS; não inventamos números)
   • Área (ha) de parte ou boletim.
   • Velocidade de propagação / ROS médio (m/min ou m/h) se constar.
   • Data e hora do registo / fonte.

C) CRONOLOGIA
   • Detecção, ataque, controlo, extinção (mesmo aproximada).

D) SE EXISTIR
   • Sequência térmica / LWIR multi-passagem com timestamps e CRS.
   • Metadados do sensor; meteorologia local; combustível do sector.

E) CONDIÇÕES DE USO
   • Uso interno, sem redistribuir dados brutos sem acordo.
   • Posso assinar nota de uso / NDA breve se necessário.

Não pedimos todo o arquivo histórico: 1–3 fogos bem documentados bastam.
Preferimos um fogo COMPLETO a muitos parciais.
"""

PACK_EN = """\
WHAT WE MEAN BY A "COMPLETE FIRE" package (ideal; any releasable subset helps):

A) GEOMETRY
   • Final vector perimeter (SHP / GPKG / GeoJSON / KMZ).
   • If available: multi-hour or multi-day sequence for the same fire.
   • CRS and date/time for each geometry.

B) OPERATIONAL ANCHOR (to validate ROS; we never invent numbers)
   • Area (ha) from official report.
   • Mean spread rate / ROS (m/min or m/h) if recorded.
   • Report date/time and source.

C) CHRONOLOGY
   • Detection, attack, control, extinction (even approximate).

D) IF AVAILABLE
   • Multi-pass thermal / LWIR with timestamps + CRS.
   • Sensor metadata; local weather; fuel map for the sector.

E) USE CONDITIONS
   • Internal project use only; no redistribution of raw third-party data.
   • Happy to sign a short data-use note / NDA.

We do not need the full archive: 1–3 well-documented fires are enough.
One COMPLETE fire is more valuable than many partial ones.
"""


def load_oauth_client() -> dict:
    raw = json.loads(OAUTH_PATH.read_text(encoding="utf-8"))
    return raw.get("installed") or raw.get("web") or raw


def get_access_token() -> str:
    creds = json.loads(CRED_PATH.read_text(encoding="utf-8"))
    client = load_oauth_client()
    # Always refresh for long batch
    data = urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read().decode())
    creds["access_token"] = tok["access_token"]
    if "expires_in" in tok:
        creds["expiry_date"] = int((time.time() + int(tok["expires_in"])) * 1000)
    CRED_PATH.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    return creds["access_token"]


def build_message(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
) -> dict:
    msg = MIMEMultipart("alternative")
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["From"] = "me"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {"raw": raw}


def send_message(token: str, message: dict) -> dict:
    data = json.dumps(message).encode("utf-8")
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def emails() -> list[dict]:
    """List of outbound messages. id used for logging."""
    return [
        {
            "id": "pt_icnf",
            "to": ["geral@icnf.pt"],
            "cc": [],
            "subject": (
                "Pedido de dados — fogos rurais COMPLETOS "
                "(perímetros + âncoras + cronologia; uso interno não comercial)"
            ),
            "body": f"""Exmos. Senhores do ICNF,

Chamo-me Alonso Alvira Ballano. Desenvolvo um projeto próprio de dinâmica de
frente de incêndio: estimativa de ROS a partir de termografia aérea e
perímetros multi-fonte, com cartão de decisão (GO / HOLD / ABSTAIN) e sem
publicar dados brutos de terceiros.

Peço, se for libertável, dados de 1 a 3 fogos rurais recentes (2024–2026)
o mais «completos» possível — ou o reencaminhamento para a equipa de
cartografia / AGIF / geoCATÁLOGO adequado.

{PACK_PT}

Já consultarei o geoCATÁLOGO (https://geocatalogo.icnf.pt/). Qualquer formato
serve (SHP, GPKG, GeoJSON, KMZ, PDF de parte).

Muito obrigado pela atenção,
{SIGNATURE_PT}""",
        },
        {
            "id": "pt_agif",
            "to": ["agif@agif.pt"],
            "cc": [],
            "subject": (
                "Pedido de contacto técnico / dados — fogos rurais completos (SGIFR; uso interno)"
            ),
            "body": f"""Exmos. Senhores da AGIF,

Sou Alonso Alvira Ballano e desenvolvo um projeto próprio de dinâmica de
frente (ROS a partir de termografia aérea + perímetros multi-fonte). Não
redistribuo dados brutos de terceiros.

Solicito, se possível:
1) Contacto da equipa que gere dados espaciais / cartografia de fogos no
   âmbito do SGIFR;
2) Para 1–2 fogos recentes bem documentados, o pacote «fogo completo»
   descrito abaixo (ou o que for libertável);
3) Ou reencaminhamento para ICNF cartografia / outro organismo competente.

{PACK_PT}

Qualquer formato é bem-vindo. Posso assinar nota de uso.

Com os melhores cumprimentos,
{SIGNATURE_PT}""",
        },
        {
            "id": "es_valencia_dgpif",
            "to": ["dgpif@gva.es"],
            "cc": [],
            "subject": (
                "Solicitud de datos — incendios COMPLETOS C. Valenciana "
                "(perímetros + anclas + cronología; uso interno no comercial)"
            ),
            "body": f"""Estimados/as de la Dirección General de Prevención de Incendios Forestales,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
en incendios forestales: ROS desde termografía aérea, perímetros multi-fuente
y tarjeta de decisión (GO / HOLD / ABSTAIN). No redistribuyo crudos de terceros.

Si es liberable para uso interno, solicito 1–2 incendios recientes en la
Comunitat Valenciana lo más completos posible (o reenvío a SIGIF / cartografía).

{PACK_ES}

Cualquier formato vale (SHP, GPKG, GeoJSON, KMZ, PDF de parte). Un incendio
completo es preferible a muchos parciales.

Gracias y un saludo,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_aragon",
            "to": ["incendios@aragon.es"],
            "cc": ["gestionforestal@aragon.es"],
            "subject": (
                "Solicitud de datos — incendios COMPLETOS Aragón "
                "(perímetros multi-hora + Vp/ha + cronología; uso interno)"
            ),
            "body": f"""Estimados/as del servicio de incendios forestales / gestión forestal de Aragón,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
(ROS desde termografía aérea y perímetros multi-fuente). No redistribuyo datos
brutos de terceros.

Si es liberable, ruego para 1–2 incendios recientes en Aragón el paquete de
«incendio completo» (o el subconjunto que puedan compartir):

{PACK_ES}

Si el buzón correcto es otro (cartografía, INFOAR, ST provincial), agradecería
el reenvío.

Un saludo y gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_navarra",
            "to": ["centralmedioambiente@navarra.es"],
            "cc": [],
            "subject": (
                "Solicitud / reenvío — incendios COMPLETOS Navarra "
                "(perímetros + partes + cronología; uso interno)"
            ),
            "body": f"""Estimados/as del servicio de Medio Ambiente del Gobierno de Navarra,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
en incendios (ROS multi-fuente + perímetros). No redistribuyo crudos.

Si es liberable, solicito 1–2 incendios recientes en Navarra con el paquete
«incendio completo» abajo, o el reenvío al servicio de prevención/extinción /
cartografía competente.

{PACK_ES}

Cualquier formato vale. Uso estrictamente interno.

Gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_canarias_grafcan",
            "to": ["idecanarias@grafcan.com"],
            "cc": ["atencionalcliente@grafcan.com"],
            "subject": (
                "Consulta / solicitud — perímetros de incendios forestales "
                "Canarias (paquete incendio completo; uso interno)"
            ),
            "body": f"""Estimados/as de IDECanarias / GRAFCAN,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
de incendio (uso interno, no comercial; sin redistribuir crudos).

¿Existe capa o servicio (WMS/WFS/descarga) de perímetros de incendios
forestales recientes en Canarias? Si es público, basta el enlace.

Si requiere solicitud al productor (Cabildo / Gobierno de Canarias), indiquen
trámite o buzón. Idealmente buscamos 1–2 incendios con paquete completo:

{PACK_ES}

Gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "fr_valabre_opendfci",
            "to": ["geomatique@valabre.com"],
            "cc": ["contact@valabre.com"],
            "subject": (
                "Data request — COMPLETE wildfire packages "
                "(perimeters + anchors + chronology; non-commercial internal use)"
            ),
            "body": f"""Dear OPEN DFCI / Entente Valabre team,

My name is Alonso Alvira Ballano. I develop an independent wildfire
front-dynamics project (ROS from aerial thermal sequences + multi-source
perimeters + decision card GO/HOLD/ABSTAIN). I do not redistribute third-party
raw data.

If releasable for internal research/validation, I request 1–2 recent French
fires as complete as possible, or a pointer to the correct data owner
(departmental fire GIS / BDIFF contributors / ONF DFCI).

{PACK_EN}

Public DFCI equipment layers via OPEN DFCI are also welcome.
I can sign a short data-use note. English or French is fine.

Best regards,
{SIGNATURE_EN}""",
        },
        {
            "id": "fr_inrae_international",
            "to": ["international@inrae.fr"],
            "cc": [],
            "subject": (
                "Request for referral — wildfire data / RECOVER units "
                "(complete fire packages; non-commercial research)"
            ),
            "body": f"""Dear INRAE International Office,

I am Alonso Alvira Ballano, developing an independent fire-front dynamics
project (aerial thermal ROS + multi-source perimeters) for research and
operational validation in Spain, expanding to Portugal and France.

Could you kindly forward this request to the relevant wildfire research units
(e.g. UMR RECOVER Aix-en-Provence or other DFCI/fire ecology groups)?

I am looking for releasable research datasets or institutional contacts for
1–2 well-documented fires:

{PACK_EN}

Thank you for any referral,
{SIGNATURE_EN}""",
        },
        {
            "id": "eu_effis_followup",
            "to": ["jrc-effis@ec.europa.eu"],
            "cc": [],
            "subject": (
                "Follow-up data request — burnt area / complete fire layers "
                "Spain + Portugal + France 2024–2026 (research, non-commercial)"
            ),
            "body": f"""Dear EFFIS team,

I contacted you on 2026-07-16 regarding BA perimeters for Castilla-La Mancha.
I write again with a clearer multi-country request for research/internal use
(no redistribution of raw third-party data).

Project: independent fire-front dynamics (aerial LWIR ROS + multi-source
perimeters + audited decision card). I already use public CEMS delineations
where available; I need better BA/perimeter vectors where releasable.

Request:
1) Burnt area / fire perimeter vectors for selected large fires in Spain,
   Portugal and France (2024–2026), with mapping/acquisition dates if possible;
2) Or guidance to national correspondents / the preferred online data request
   form for multi-country BA layers;
3) Any metadata that helps assemble a "complete fire" package:

{PACK_EN}

I will also (re)submit the EFFIS data request form.
Any format (SHP/GPKG/GeoJSON) is welcome.

Thank you,
{SIGNATURE_EN}""",
        },
        {
            "id": "es_pablo_geacam_completo",
            "to": ["pablo.arroyobretano@geacam.com"],
            "cc": ["contacto@geacam.com"],
            "subject": (
                "Seguimiento — gracias pack 0308 / Hellín; "
                "¿paquete multi-IF lo más completo posible?"
            ),
            "body": f"""Hola Pablo,

gracias de nuevo por Tobarra (KMZ multi-hora) y por el pack 0308 (Hellín KMZ +
boletín UNAP, Cardoso, La Estrella). Ya lo tenemos ingestado en el proyecto;
nos ha sido muy útil.

Para cerrar validación multi-incendio con el criterio de «incendio completo»
(geometría + ancla Vp/ha con hora + cronología + térmica si hay), ¿sería
posible, cuando puedas y sin prisa, completar lo liberable en 1–2 IF más?

En particular, si en algún momento hay:
• Vp o ha de parte con fecha-hora para Cardoso (o confirmación de fuente);
• Perímetros multi-hora adicionales Hellín/Estrella/Cardoso en vector;
• Alguna secuencia térmica exportable (aunque sea un subset) de un IF con
  buena cobertura.

Resumen de lo que llamamos incendio completo (cualquier subconjunto ayuda):

{PACK_ES}

Uso interno; sin publicar crudos sin acuerdo. Cualquier formato vale.

Un saludo y gracias otra vez por el apoyo,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_galicia_followup",
            "to": ["defensadomonte.mediorural@xunta.gal"],
            "cc": ["forestal.mediorural@xunta.gal"],
            "subject": (
                "Seguimiento — solicitud datos incendios COMPLETOS Galicia "
                "(traslado a Extinción; uso interno)"
            ),
            "body": f"""Estimados/as de la Dirección Xeral de Defensa do Monte,

El 22 de julio me indicaron que daban traslado de mi petición a Extinción.
Escribo un único seguimiento educado por si ya hay canal o datos liberables.

Proyecto propio de dinámica de frente (ROS desde termografía + perímetros).
No redistribuyo crudos. Solicito 1–2 incendios gallegos recientes lo más
completos posible, o reenvío al buzón de Extinción / cartografía competente:

{PACK_ES}

Si el traslado sigue en curso, basta con el contacto correcto.
Gracias por su tiempo,

{SIGNATURE_ES}""",
        },
        {
            "id": "es_asema_followup",
            "to": ["gerencia.asema@juntadeandalucia.es"],
            "cc": [],
            "subject": (
                "Seguimiento — proyecto dinámica de frente; "
                "incendio COMPLETO ops Andalucía (además de REDIAM)"
            ),
            "body": f"""Estimados/as de la Gerencia ASEMA / Agencia de Emergencias de Andalucía,

El 22 de julio escribí sobre validación de dinámica de frente. REDIAM ya nos
facilitó el acceso a perímetros abiertos 2008–2025 (muchas gracias a ese
canal). Escribo un único seguimiento por si desde el lado operativo / IIFF
es liberable un «incendio completo» de 1–2 eventos recientes (no satelital
solo):

{PACK_ES}

Si el buzón correcto es otro (DG Gestión IIFF, cartografía ops), agradecería
el reenvío. Uso interno; sin redistribuir crudos.

Un saludo,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_heligrafics_followup",
            "to": ["info@heligrafics.net"],
            "cc": [],
            "subject": (
                "Seguimiento — metadatos LWIR y secuencias; "
                "paquete incendio completo para validación ROS"
            ),
            "body": f"""Estimados/as de Heligrafics,

El 16 de julio les escribí sobre metadatos de sensor y posible ampliación de
secuencias térmicas (proyecto propio de dinámica de frente en CLM, con
material GEACAM/Heligrafics). Escribo un único seguimiento.

Si es viable, nos ayudaría cualquier de esto (aunque sea un IF piloto):

{PACK_ES}

En particular: metadatos de exportación LWIR (timestamps, CRS, GSD, FOV) y,
si existe política de cesión, 1 secuencia multi-pasada de un incendio con
buen solape temporal.

Uso interno de validación; sin redistribuir crudos sin acuerdo.

Gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_uclm_moreno",
            "to": ["JoseM.Moreno@uclm.es"],
            "cc": ["Jorge.Heras@uclm.es"],
            "subject": (
                "Proyecto propio dinámica de frente CLM — "
                "posible colaboración / datos o reenvío (incendio completo)"
            ),
            "body": f"""Estimado Prof. Moreno / equipo Grupo Fuego UCLM,

Soy Alonso Alvira Ballano (ingeniero informático). Desarrollo un proyecto
propio de dinámica de frente en incendios de Castilla-La Mancha a partir de
secuencias térmicas aéreas y perímetros multi-fuente, con validación honesta
(anclas Vp/ha, abstención si no hay fiabilidad).

No pido acceso privilegiado a redes operativas: busco, si es posible,
• reenvío a contactos de datos (GEACAM/INFOCAM ya en hilo; otras CCAA),
• feedback científico sobre el criterio de «incendio completo» para validar ROS,
• o datasets de investigación liberables.

{PACK_ES}

Uso no comercial / interno. Encantado de compartir un one-pager del proyecto
si les resulta útil.

Un saludo,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_paucosta",
            "to": ["info@paucostafoundation.org"],
            "cc": [],
            "subject": (
                "Independent fire-front project — request for data contacts "
                "(complete fire packages ES/PT/FR)"
            ),
            "body": f"""Dear Pau Costa Foundation team,

I am Alonso Alvira Ballano. I develop an independent wildfire front-dynamics
project (aerial thermal ROS + multi-source perimeters + audited GO/HOLD/ABSTAIN
decision card) focused on Spain, expanding data outreach to Portugal and France.

I would be grateful for any referral to data holders or practitioners who can
share releasable "complete fire" packages (or the right institutional mailbox):

{PACK_EN}

I am not asking for emergency/112 channels — only research/ops GIS and
post-event packages. Happy to share a short project one-pager.

Thank you,
{SIGNATURE_EN}""",
        },
        {
            "id": "es_secf",
            "to": ["secforestales@secforestales.org"],
            "cc": [],
            "subject": (
                "Consulta red SECF — contactos datos incendios completos "
                "(perímetros + anclas; proyecto propio no comercial)"
            ),
            "body": f"""Estimados/as de la SECF,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
en incendios (ROS desde termografía aérea + perímetros multi-fuente).

¿Podrían orientarme o reenviar a grupos de trabajo / personas de contacto en
CCAA o centros que gestionen cartografía de incendios y partes liberables?

Busco 1–3 «incendios completos» para validación (no datos en tiempo real 112):

{PACK_ES}

Gracias por cualquier orientación,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_aself",
            "to": ["administracion@aself.org"],
            "cc": ["comunicacion@aself.org"],
            "subject": (
                "Consulta red ASELF — contactos datos / perímetros "
                "incendios completos (proyecto propio no comercial)"
            ),
            "body": f"""Estimados/as de ASELF,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
y productos de apoyo a la decisión en incendios forestales (no orden táctica).

¿Conocen buzones o personas de cartografía / análisis de incendios en CCAA
(además de CLM) o en Portugal/Francia a quienes pueda solicitar de forma
formal un paquete de «incendio completo» liberable?

{PACK_ES}

Cualquier reenvío o contacto público es de gran ayuda.

Gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "pt_prociv_optional",
            "to": ["geral@prociv.pt"],
            "cc": [],
            "subject": (
                "Pedido de reencaminhamento — dados de fogos rurais completos "
                "(não emergência 112; uso interno investigação)"
            ),
            "body": f"""Exmos. Senhores da ANEPC,

Sou Alonso Alvira Ballano. Desenvolvo um projeto próprio de dinâmica de frente
de incêndio (ROS a partir de termografia aérea + perímetros). Não se trata de
um pedido de emergência nem do canal 112.

Solicito apenas o reencaminhamento para o serviço / organismo que possa
facilitar (ou indicar) dados libertáveis de 1–2 fogos rurais documentados
(ICNF / AGIF / cartografia), no formato de «fogo completo»:

{PACK_PT}

Se o canal correto for exclusivamente ICNF/AGIF, basta a confirmação.

Com os melhores cumprimentos,
{SIGNATURE_PT}""",
        },
        {
            "id": "es_masterfuego_udl",
            "to": ["etseafiv.coordmfuego@udl.cat"],
            "cc": [],
            "subject": (
                "Máster FUEGO — consulta red / contactos datos "
                "incendios completos (proyecto propio)"
            ),
            "body": f"""Estimados/as de la coordinación del Máster FUEGO,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
en incendios forestales (ROS térmico aéreo + perímetros multi-fuente).

¿Podrían orientarme a docentes o contactos de red (España/Portugal/Francia)
que gestionen o conozcan fuentes de perímetros y partes liberables para
validación? Busco el criterio de «incendio completo»:

{PACK_ES}

No pido datos operativos de 112. Uso interno / no comercial.

Gracias,
{SIGNATURE_ES}""",
        },
        {
            "id": "es_cdf_cyl_wait_skip",
            "skip": True,
            "reason": "CyL silence rule until ~2026-08-17",
            "to": ["centrofuego@jcyl.es"],
            "subject": "(SKIP) CyL silence",
            "body": "",
        },
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Only send these message ids",
    )
    ap.add_argument(
        "--delay",
        type=float,
        default=2.5,
        help="Seconds between sends",
    )
    args = ap.parse_args()

    items = [e for e in emails() if not e.get("skip")]
    if args.only:
        want = set(args.only)
        items = [e for e in items if e["id"] in want]

    print(f"messages_to_send={len(items)} dry_run={args.dry_run}")
    token = None if args.dry_run else get_access_token()
    results = []

    for i, e in enumerate(items):
        entry = {
            "id": e["id"],
            "to": e["to"],
            "cc": e.get("cc") or [],
            "subject": e["subject"],
            "status": "pending",
            "gmail_id": None,
            "error": None,
            "ts_utc": datetime.now(UTC).isoformat(),
        }
        print(f"[{i + 1}/{len(items)}] {e['id']} -> {e['to']}")
        if args.dry_run:
            entry["status"] = "dry_run"
            results.append(entry)
            continue
        try:
            msg = build_message(e["to"], e["subject"], e["body"], e.get("cc"))
            resp = send_message(token, msg)
            entry["status"] = "sent"
            entry["gmail_id"] = resp.get("id")
            print("  SENT", resp.get("id"))
        except urllib.error.HTTPError as err:
            body = err.read().decode(errors="replace")
            entry["status"] = "error"
            entry["error"] = f"{err.code}: {body[:500]}"
            print("  ERROR", entry["error"][:200])
            if err.code in (401, 403):
                token = get_access_token()
        except Exception as ex:  # noqa: BLE001
            entry["status"] = "error"
            entry["error"] = str(ex)
            print("  ERROR", ex)
        results.append(entry)
        if i < len(items) - 1 and not args.dry_run:
            time.sleep(args.delay)

    LOG_PATH.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "dry_run": args.dry_run,
                "n": len(results),
                "n_sent": sum(1 for r in results if r["status"] == "sent"),
                "n_error": sum(1 for r in results if r["status"] == "error"),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("log", LOG_PATH)
    print(
        "summary sent=",
        sum(1 for r in results if r["status"] == "sent"),
        "error=",
        sum(1 for r in results if r["status"] == "error"),
    )


if __name__ == "__main__":
    main()
