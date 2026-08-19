# Prior art disclosure — Relator

Required by All Things Agentic rules: *“Projects must be newly created during the Submission Period… must disclose any other pre-existing code or work incorporated.”*

## New in this slice (hackathon period)

- Source-board schema and quorum (`board.py`)
- Scout FIRMS pulse + deterministic Maps grounding (`scout.py`, `maps_grounding.py`)
- Clerk drop classifier + cited-ha extractor (`clerk.py`)
- Fiscal / Model Armor stand-in (`fiscal.py`)
- Event orchestrator, demo clock, HTML board, Cloud Run handler, ADK tool wrappers
- This README / architecture story

## Pre-existing (WildfireFrontDynamics)

Imported, not rewritten, used **only as tools**:

| Symbol | Role in Relator |
|--------|-----------------|
| `wildfire_front.product.decide_service.decide_from_request` | Sealed **judge**. Not an LLM. |
| `wildfire_front.product.operator_intake.receive_files` | Optional GeoTIFF inbox (JPG already rejected there). |
| Product rails | GO_Q partial, fusion ON ≠ dispatch, FIRMS ≠ burned area, IoU ≠ ROS |

Relator does **not** promote `ml_product_go`, does **not** change `docs/CURRENT_STATE.md`, does **not** reopen FREEZE_ML, and does **not** claim a field GO.

## What Relator is not allowed to claim

- Tactical dispatch / resource orders / evacuations
- Catalog holdout IoU as live certainty
- RCDA / Caldor as product scores
- Invented ROS or hectares
- GO_Q complete
