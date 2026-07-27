# WildfireFrontDynamics — one-pager (EU partners)

**Status:** Independent research / open-source product path · **Spain (Castilla-La Mancha domain)**  
**Contact:** Alonso Alvira Ballano · alonso.alvbal@gmail.com · https://github.com/ (pendiente)  
**Date:** 2026-07

---

## Problem

Mediterranean megafires overwhelm command posts with **fragmented data** (satellites, press, radio, air assets). Many tools show maps; few enforce **when not to recommend action**. False confidence is operationally dangerous.

## Solution

**Decision-support software** that fuses:

1. **Open intelligence** — NASA FIRMS multi-sensor, Sentinel-2 STAC, CEMS watch, daily cadence packs  
2. **Ops thermal (when available)** — drone / LWIR incident ROS path  
3. **Fire Decision Card** — **GO / HOLD / ABSTAIN** with confidence, policy (field_ops vs research), audit hashes  

**Hard rule:** no field GO from open-only FIRMS/press. Press hectares never become confirmed anchors.

## Evidence already built

| Asset | Note |
|-------|------|
| Open pack **La Mierla (GU) Jul 2026** | Multi-sensor FIRMS timeline, maps, HOLD cards, week package |
| ML CLM ensemble track | Holdout metrics on real CLM fires (separate from live dispatch) |
| Reliability / abstention design | Silent-GO prevented by product gates |
| Reproducible CLI | Daily open-day runner, decide API, forensic replay |

## What we seek

| Partner type | What we need | What you get |
|--------------|--------------|--------------|
| **Civil protection end-user** | Pilot + letter of support; optional LWIR samples | Software pilot, open packs, decision audit trail |
| **University / RTO** | Consortium leadership on UCPM / Horizon | SME/tech work package (software, EO fusion, metrics) |
| **EU SME** (PT/IT/GR/FR) | SUDOE / multi-country consortium seat | Joint demo Mediterranean wildfire corridor |

## Fit for EU instruments

- **UCPM** Prevention & Preparedness / Knowledge Network — tools for responders, cross-border readiness  
- **Interreg SUDOE** — SW Europe wildfire prevention & management  
- **Horizon Europe** — disaster-resilient societies / climate adaptation (as tech partner)  
- **EIC / national (NEOTEC)** — later, once a legal entity exists  

## Non-claims (honesty)

- Not a replacement for official perimeter or EGIF statistics  
- Not automatic tactical dispatch  
- Google Maps tiles are not scraped; deep-links + open EO only  

## Ask (next 30 days)

1. 30-minute call  
2. Feedback on pilot scope (1 region, 1 fire season)  
3. If aligned: **letter of support** draft for next UCPM / Interreg / Horizon call  

---

*Repository and pack demos available under NDA or open license discussion.*
