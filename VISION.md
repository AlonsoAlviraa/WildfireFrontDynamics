# 🎯 VISION — WildfireFrontDynamics

## What We Build

A machine-learning system that predicts **next-day wildfire spread** using satellite imagery, meteorological data, and terrain features. The system segments a map into "will burn" vs "won't burn" cells, enabling emergency responders to anticipate fire front movement.

## Why It Matters

Wildfires destroy millions of hectares annually. Predicting where a fire will spread **24 hours in advance** saves lives, optimizes resource deployment, and reduces economic loss. Our system targets **Castilla-La Mancha, Spain** as the operational domain, with global applicability.

## North Star Metric

| Metric | Target | Current |
|---|---|---|
| **IoU (Intersection over Union)** | **>0.30** | 0.002 |
| **Recall** | **>0.50** | 0.002 |

Benchmark reference: NDWS paper (Hu et al., NeurIPS 2023) achieves IoU=0.42 with U-Net.

## Core Principles

1. **Physics-informed ML** — Combine Rothermel's fire spread equations with deep learning
2. **Leak-free evaluation** — Train/val/test splits are geographically disjoint
3. **Real-world deployability** — Must work on real GeoTIFF data from Spanish wildfires (Tobarra, La Estrella)
4. **Iterative improvement** — Loop engineering: hypothesis → experiment → measure → learn

## Architecture Direction

```
Satellite + Weather Data → U-Net Segmentation → Fire Spread Probability Map
                                                      ↓
                                              Meta-Labeler (RandomForest)
                                                      ↓
                                              Trustworthy Predictions
```

## Current Phase

We are in **Phase 1: Architectural Overhaul** — transitioning from A3C-LSTM (per-cell, batch_size=1) to U-Net (full-patch, batch_size=32). Three experiments (v10-v12) proved the bottleneck is architectural.

## Success Definition

When a firefighter in Castilla-La Mancha can upload today's fire perimeter + weather data and receive a reliable 24-hour spread prediction with **IoU > 0.30**.