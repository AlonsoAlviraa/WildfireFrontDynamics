# Wildfire front / next-day wildfire spread ML product (like NDWS + residual U-Net small ensemble ~1M params on legacy17 64x64 patches): Are we leaving performance on the table by NOT using larger U-Nets (or transformers/foundation models) and larger multi-source datasets (WildfireSpreadTS full ~48GB, FireBench, multi-fire LOFO, UAV thermal)? How does industry and SOTA research (2023-2026) actually do multi-horizon fire perimeter / ROS / spread forecasting for operational sell (not paper-only)? What typically fails when scaling model size or data? Critical commercial constraint: next-day-only prediction is insufficient to sell to emergency services — need multi-lead-time forecasts e.g. 1h, 3h, 5h, 12h, 24h. Compare physics/cellular automata/Rothermel/WRF-SFIRE/Prometheus vs pure DL vs hybrid; multi-step rollout vs multi-horizon heads; temporal resolution of satellite vs drone vs ground sensors. Evidence-based recommendations for a dual-product stack (lab ML mask vs field_ops ROS geometry).

(Synthesis agent returned no text; raw verified claims below.)

1. On the Next Day Wildfire Spread (NDWS) benchmark (64×64 km patches at 1 km resolution, 12 multimodal channels, ~18,545 fire samples), Huot et al.'s residual convolutional autoencoder (ResBlock U-Net-style segmentation model) achieved AUC-PR 28.4%, precision 33.6%, and recall 43.1% for next-day fire mask prediction, beating random forest (AUC-PR 22.5%) and logistic regression (19.8%) and far above a fire-persistence baseline (AUC-PR 11.5%).
   Source: Huot et al., Next Day Wildfire Spread (arXiv:2112.02447 / IEEE TGRS 2022)
   URL: https://arxiv.org/pdf/2112.02447
2. On WildfireSpreadTS (WSTS; multi-day extension of NDWS-style remote-sensing inputs, 12-fold leave-one-year-out CV), Gerard et al. reported mean average precision (AP): ResNet18 U-Net ~14.4M params AP 0.341 (1-day, Multi features) and 0.344 (5-day, Multi); ConvLSTM 240k params AP 0.310 (5-day Multi); UTAE only 1.1M params achieved the best baseline AP 0.372 (5-day Vegetation)—about 13× fewer parameters than the Res18 U-Net while outperforming it by up to 3.9 percentage points.
   Source: Gerard, Zhao, Sullivan — WildfireSpreadTS (NeurIPS 2023 Datasets and Benchmarks)
   URL: https://proceedings.neurips.cc/paper_files/paper/2023/file/ebd545176bdaa9cd5d45954947bd74b7-Paper-Datasets_and_Benchmarks.pdf
3. On the same WSTS leave-one-year-out protocol, Lahrichi et al. (WACV 2026) raised single-day Res18-Unet AP from 0.341 to 0.468 (Multi features, 14.3M params) via pretraining, focal loss, and AP-based model selection (~37% relative gain). Larger/attention models did not win: Res50-Unet 32.5M AP 0.459; SwinUnet-Tiny 27.2M AP 0.437; SegFormer-B2 27.5M AP 0.436. Overall SOTA was UTAE with ResNet-18 encoder at 14.6M params and AP 0.478 (5-day Vegetation); plain UTAE stayed at 1.1M params with AP 0.459 (5-day Multi).
   Source: Lahrichi et al., Improved Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark (WACV 2026 / arXiv:2502.12003)
   URL: https://openaccess.thecvf.com/content/WACV2026/papers/Lahrichi_Improved_Wildfire_Spread_Prediction_with_Time-Series_Data_and_the_WSTS_WACV_2026_paper.pdf
4. Lightweight transform-domain residual U-Nets (~0.1–0.4M params) match or beat multi-million-parameter ResNet U-Nets on next-day spread. TD-FusionUNet (Hadamard + DCT latent spaces) reached F1 0.591 with 370k parameters on WildfireSpreadTS versus ResNet18 U-Net F1 0.589 at 14M parameters; on Google NDWS with customized preprocessing (including both-day target setting), TD-FusionUNet base-8 got F1 0.702 / IoU 0.555 at 93k parameters versus Huot-style 2D-CNN autoencoder F1 0.621 (78k) under the same customized both-day protocol.
   Source: Luo et al., U-Net with Hadamard Transform and DCT Latent Spaces for Next-Day Wildfire Spread Prediction (arXiv:2602.11672, 2026)
   URL: https://arxiv.org/pdf/2602.11672
5. ShearFuse-UNet (WHT + DCT + Shearlet residual branches inside a tiny U-Net, 267k parameters) achieved F1 0.596 and IoU 0.424 on WildfireSpreadTS, outperforming ResNet18-based U-Net (14M params, F1 0.589) and larger Swin-UNet variants (up to 99M params) while using 1.35 GFLOPs and ~3.03 ms/sample inference (128×128 input)—a roughly 52× parameter reduction versus ResNet18-UNet with better F1.
   Source: Meco et al., ShearFuse-UNet (arXiv:2606.14071, 2026)
   URL: https://arxiv.org/html/2606.14071v1
6. Under a strict next-day-only evaluation on Google NDWS (64×64 patches; unknown labels excluded), FireSenseNet (dual-branch residual CNN with cross-attentive fusion, 3.01M params) achieved F1 0.4176 and AUC-PR 0.3435. Vision Transformers underperformed: SegFormer 11.3M params F1 0.3502 / AUC-PR 0.2699; Small Transformer 1.9M F1 0.3490. A single-stream Baseline CNN at ~1.15M params reached F1 0.3933 / AUC-PR 0.3354. FireSenseNet inference latency was ~3.1 ms (2.52 GFLOPs) vs SegFormer ~6.8 ms.
   Source: Han et al., FireSenseNet (arXiv:2604.07675, 2026)
   URL: https://arxiv.org/html/2604.07675v1
7. Evaluation protocol strongly affects reported NDWS metrics: predicting both previous-day and next-day fire masks and treating unknown (−1) pixels as non-fire inflated F1 by ~44–50% (e.g., FireSenseNet clean F1 0.4176 → inflated 0.6033; SegFormer 0.3502 → 0.5252). This explains why some lightweight U-Net papers report F1 ~0.6–0.7 on NDWS under customized/both-day settings while strict next-day-only scores remain near Huot’s ~0.35–0.42 F1 / [2m▸ done   verify:recency [0m
 ~0.28–0.34 AUC-PR range for residual CNNs of order ~1M parameters.
   Source: Han et al., FireSenseNet evaluation-protocol analysis (arXiv:2604.07675, 2026)
   URL: https://arxiv.org/html/2604.07675v1
8. Across 2023–2026 NDWS/WSTS-style next-day wildfire mask benchmarks, residual CNN / lightweight U-Net models near ~0.3–3M parameters (including Huot residual autoencoders, ~1.1M UTAE, ~1.15M baseline CNNs, and sub-million transform-domain residual U-Nets) are competitive with or better than larger ResNet50 U-Nets (~32M), Swin/SegFormer vision transformers (~11–27M+), and pure Transformers; larger capacity does not consistently improve leave-one-year-out AP/F1 under severe class imbalance and limited samples, while operational cost favors the ~1M-class models (sub-10 ms inference, ~1–3 GFLOPs on 64×64/128×128 patches).
   Source: Synthesis of Gerard et al. 2023, Lahrichi et al. WACV 2026, Luo et al. 2026, Meco et al. 2026, Han et al. 2026
   URL: https://arxiv.org/html/2502.12003v2
9. WildfireSpreadTS is released as a 48.4 GB zip on Zenodo (v1.0, Oct 2023) and contains 13,607 daily multi-channel images across 607 U.S. wildfire events (Jan 2018–Oct 2021), with full multi-day time series of active-fire detections plus fuel, topography, and weather variables for 24-hour spread prediction.
   Source: Zenodo record 8006177 (WildfireSpreadTS dataset page)
   URL: https://zenodo.org/records/8006177
10. Relative to mono-temporal Next Day Wildfire Spread (~18,445 samples of 64×64 km patches at 1 km with MODIS fire masks), WildfireSpreadTS enables multi-temporal modeling, uses higher-resolution VIIRS active-fire masks, adds land-cover and weather-forecast channels (23 total), and resamples to 375 m—addressing NDWS limitations of coarse 1 km fire masks and single-day inputs.
   Source: Kaggle Next Day Wildfire Spread dataset description; arXiv WSTS+ paper characterizing WSTS vs NDWS
   URL: https://www.kaggle.com/datasets/fantineh/next-day-wildfire-spread
11. The WSTS benchmark evaluates models with rigorous 12-fold leave-one-year-out cross-validation so every test fold uses fires from a previously unseen year, a stricter real-world protocol than random patch splits common on smaller single-source corpora.
   Source: arXiv:2502.12003v2 (Advancing Time Series Wildfire Spread Prediction; Lahrichi et al.)
   URL: https://arxiv.org/html/2502.12003v2
12. On WSTS, published baseline Res18-Unet / UTAE average precision was roughly AP 0.32–0.37 (single-day) and up to ~0.37 (multi-day); improved modeling raised single-day AP by ~37% and multi-day by ~28%, reaching a new overall SOTA of AP 0.478 with UTAE(Res18) on vegetation features under leave-one-year-out evaluation—showing multi-temporal multi-fire corpora support higher measured performance than original WSTS baselines, though absolute AP remains moderate.
   Source: arXiv:2502.12003v2 Table 2 and contributions (Lahrichi et al.)
   URL: https://arxiv.org/html/2502.12003v2
13. WSTS+ expands WSTS from 4 to 8 years (2016–2023), 607→1,005 fire events, 13,607→24,462 images (+79.8%), and more active-fire pixels; yet mean test AP fell by roughly 0.1 versus WSTS and extra years did not unlock gains from larger models—revealing data heterogeneity (year-to-year domain/concept shift and variable label difficulty) as a remaining coverage gap when scaling multi-fire corpora.
   Source: arXiv:2502.12003v2 (Tables 4–5 and Section 7.2)
   URL: https://arxiv.org/html/2502.12003v2
14. FireBench is a high-fidelity LES ensemble of 117 controlled wildfire simulations (wind×slope), each with 1.35 billion mesh points on a 1500×250×1800 m domain, totaling about 1.36 PiB of 3D time-series flow-field data released to reduce observational data scarcity for ML fire-prediction model development.
   Source: arXiv:2406.08589 PDF (Wang et al., FireBench / high-fidelity ensemble framework)
   URL: https://arxiv.org/pdf/2406.08589
15. Google Research positions FireBench as enabling parametric study of fire–atmosphere coupling and training of robust, interpretable ML models via dense 3D variables beyond sparse observational fire masks; the ensemble was generated in under a week with ~200k TPU hours using SWIRL-FIRE+Vizier—changing the performance ceiling by supplying physics-rich labels unavailable in small remote-sensing patch corpora, while remaining simulation (not real-world multi-fire) data.
   Source: Google Research Blog: FireBench (July 16, 2024)
   URL: https://research.google/blog/firebench-using-high-performance-computing-to-advance-machine-learning-and-wildfire-research/
16. Leave-one-fire-out (LOFO) cross-validation on multi-fire remote-sensing tasks yields a measurable performance drop versus within-fire or site-optimized splits: for Sentinel-2 live-tree post-fire mapping across Caldor, Dixie, and KNP fires, LOFO accuracy was 76–81% with F-scores 0.64–0.78 versus 80–85% accuracy and F-scores 0.66–0.82 for site-optimized models—quantifying how multi-fire holdout protocols expose weaker generalization than patch-level random splits on single-source corpora.
   Source: Environmental Research: Ecology (IOP) Wong et al. 2025 PDF (leave-one-fire-out cross-validation results)
   URL: https://iopscience.iop.org/article/10.1088/2752-664X/add5fd/pdf
17. MDPI Remote Sensing work on burn-severity mapping pairs Leave-One-Cluster-Out (within-fire spatial blocking) with Leave-One-Fire-Out (LOFO) specifically to quantify true across-fire generalization, indicating that multi-fire LOFO is becoming a required protocol because ordinary CV on mixed patches overstates performance on new fires.
   Source: MDPI Remote Sensing 17(22):3756 abstract (Spatially Blocked Validation Within and Across Fires)
   URL: https://www.mdpi.com/2072-4292/17/22/3756
18. FLAME 3 multi-prescribed-fire UAV RGB–radiometric-thermal data improves over single-source FLAME 1/2: combining FLAME 1&2&3 RGB reached 82.90% fire/no-fire test accuracy (highest among RGB combinations), and FLAME 3 radiometric TIFF-only input reached 91.38% accuracy (RGB-TIFF 90.95%)—outperforming FLAME 2 thermal inputs and showing multi-fire multi-modal UAV corpora raise detection performance relative to smaller single-burn patch sets.
   Source: arXiv HTML: FLAME 3 Dataset (Hopkins et al., Tables VII–VIII)
   URL: https://arxiv.org/html/2412.02831v1
19. Single-prescribed-fire UAV datasets (e.g., FLAME 1) produce highly similar samples; models trained on them suffer when generalizing to unseen fuel types, terrain, geography, weather, or time of day. FLAME 3’s six burns (pine, grass, sagebrush; AZ/OR/FL) are reported to improve generalization versus FLAME 1/2, while still covering only low-to-moderate intensity prescribed fire—not extreme wildfire behavior.
   Source: arXiv HTML: FLAME 3 Dataset (Section II-B3 Variety and Diversity of Data)
   URL: https://arxiv.org/html/2412.02831v1
20. Cross-database UAV evaluation (FireMan-UAV-RGBT boreal Finland vs FLAME-1/2 pinyon-juniper/ponderosa) shows severe domain shift: ResNet50 trained on FireMan got perfect accuracy on its own test set but F1 0.39–0.74 / accuracy 0.60–0.91 on FLAME; trained on FLAME-1 and tested on FireMan accuracy fell to ~6%—demonstrating that small single-source UAV thermal/RGB corpora do not transfer across biomes without multi-fire multi-region coverage.
   Source: University of Oulu repository PDF abstract/results for FireMan-UAV-RGBT (Kularatne et al.)
   URL: https://oulurepo.oulu.fi/bitstream/handle/10024/52595/nbnfioulu-202411076641.pdf?sequence=1
21. Remaining labeling/coverage gaps for WildfireSpreadTS-class remote-sensing spread ML include highly imbalanced and noisy active-fire labels from smoke, clouds, and detection error; year-to-year feature distribution and label-difficulty shifts (WSTS+); coarse spatial scale (375 m) relative to fireline processes; and incomplete geographic coverage outside western U.S. multi-year windows.
   Source: NeurIPS Datasets & Benchmarks 2023 abstract text for WildfireSpreadTS; arXiv:2502.12003v2 heterogeneity discussion
   URL: https://neurips.cc/virtual/2023/poster/73593
22. Rem [2m▸ stage 3: 104 claims survived; 2 refuted, 0 verifier-failed, 0 duplicate (total dropped: 2) [0m
 [2m▸ stage 4: synthesizing report from 104 verified claims [0m
 [2m▸ spawn  synthesize [0m
 [2m▸ fail   synthesize: failed to spawn grok: spawn ENAMETOOLONG [0m
 [2m▸ spawn  synthesize (retry 1) [0m
 [2m▸ fail   synthesize (retry 1): failed to spawn grok: spawn ENAMETOOLONG [0m
 [2m▸ spawn  synthesize (retry 2) [0m
 [2m▸ fail   synthesize (retry 2): failed to spawn grok: spawn ENAMETOOLONG [0m
 [2m▸ giveup synthesize: failed to spawn grok: spawn ENAMETOOLONG [0m
 [2m▸ stage 4: synthesis agent failed; returning raw claims as the report [0m
aining UAV thermal labeling/coverage gaps include imperfect RGB–thermal FOV alignment (blocking true pixel-wise fusion), conversion of radiometric values to palette JPEGs that loses temperature information, scarce pixel-level burn-severity/post-assessment labels, limited high-intensity wildfire (vs prescribed) capture, short UAV endurance and airspace constraints, and sparse publicly open multi-burn radiometric TIFF sets (full FLAME 3 often request-only).
   Source: arXiv HTML: FLAME 3 Dataset (Sections II-B, III-A image alignment / TIFF vs JPEG, and conclusion)
   URL: https://arxiv.org/html/2412.02831v1
23. Next Day Wildfire Spread explicitly encodes an uncertain label class for cloud coverage or unprocessed data in fire masks; 1 km MODIS resolution limits prediction skill especially for small fires, and mono-temporal patches encourage models to copy prior perimeters—label and resolution gaps that multi-temporal VIIRS-based WildfireSpreadTS partially mitigates but does not eliminate.
   Source: Kaggle Next Day Wildfire Spread content description; SciSpace/NDWS paper summary on 1 km resolution limits
   URL: https://www.kaggle.com/datasets/fantineh/next-day-wildfire-spread
24. FireBench remains physics-simulation data with controlled wind/slope ensembles rather than multi-fire observational LOFO benchmarks; it closes scarcity of high-resolution dynamics for ML training but leaves a sim-to-real gap relative to noisy multi-source satellite/UAV labels and does not by itself provide leave-one-fire-out observational performance guarantees.
   Source: Google Research Blog FireBench; arXiv:2406.08589 methodology
   URL: https://research.google/blog/firebench-using-high-performance-computing-to-advance-machine-learning-and-wildfire-research/
25. Nature Scientific Data TS-SatFire overview states WildfireSpreadTS baseline U-Net/ConvLSTM/UTAE results highlight the difficulty of progression prediction even on the large multi-modal multi-temporal corpus—indicating that scale and multi-fire structure alone have not made next-day spread an easy ML problem relative to smaller single-source classification/patch tasks.
   Source: Nature Scientific Data article page excerpt on TS-SatFire / WildfireSpreadTS baselines
   URL: https://www.nature.com/articles/s41597-025-06271-3
26. Technosylva’s commercial Wildfire Operations (FireRisk™) platform delivers on-demand wildfire spread simulations in under 30 seconds with real-time monitoring, deterministic and probabilistic outputs, and automatic impact/consequence analysis (structures, population, assets); it also provides enhanced weather prediction via tailored WRF models at 2 km spatial and 1-hour temporal resolution for 100+ hour forecasts used by fire agencies and utilities for near-term operations and PSPS decisions.
   Source: Technosylva – Wildfire Operations product page
   URL: https://technosylva.com/products/wildfire-operations/
27. Technosylva markets on-demand wildfire spread modeling for active incidents and proactive “what if” scenarios days in advance, plus asset-ignition risk forecasting over a multi-day (including 4-day) horizon, with situational awareness that combines advanced fire-spread prediction and forecasted weather to quantify impacts—sold to electric utilities and fire agencies for operational resource positioning, not merely next-day outlooks.
   Source: Technosylva – Electric Utilities solutions page
   URL: https://technosylva.com/electric-utilities/
28. In California utility/regulatory operational analysis, Technosylva Wildfire Analyst fire-spread simulations for damage/ignition incidents were run for a 24-hour duration and produced pixel-level rate of spread, flame length, fireline intensity, and fire type; the Initial Attack Assessment (IAA) index explicitly uses first-hour fire perimeter (no suppression) and fire-area growth between the first and second hour—showing commercial ops products are built around sub-daily (1h–2h and 24h) lead times.
   Source: CPUC Technosylva Report on PG&E PSPS Event (Oct 9–12, 2019)
   URL: https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/safety-and-enforcement-division/documents/technosylva-report-on-pge-psps-eventoct-912-2019.pdf
29. Wildfire Analyst is described as providing real-time wildfire behavior analysis and spread simulations completed in seconds, architected specifically for initial-attack situations so incident commanders can support suppression and resource allocation when time is of the essence—i.e., commercial value is tied to minute-to-hour decision windows, not next-day-only products.
   Source: Technosylva Wildfire Analyst Pocket Edition site
   URL: https://pocket.wildfireanalyst.com/
30. As of 2024 reporting, CAL FIRE used Technosylva models (weather, topography, fuels, satellite inputs) for predictions up to five days ahead, with dedicated analysts applying the models during major incidents (e.g., Park Fire); Technosylva was reported running about half a billion simulations per day in California alone for localized predictions for agencies and utilities.
   Source: Latitude Media – Technosylva firetech analysis (Oct 1, 2024)
   URL: https://www.latitudemedia.com/news/utilities-are-beginning-to-embrace-firetechs-old-guard/
31. A 2023 peer-reviewed evaluation of California operational fire-spread models (Wildfire Analyst Enterprise automatic simulations vs FireGuard observed growth for 1,853 initial-attack wildfires) concluded performance was accurate enough for real-time operations, especially with field-data adjustment/calibration modes—validating multi-incident automated ROS/spread prediction for emergency initial attack rather than only next-day planning.
   Source: TEMA Project summary of Cardil et al., International Journal of Wildland Fire (2023)
   URL: https://tema-project.eu/articles/performance-operational-fire-spread-models-california
32. OroraTech’s commercial Fire Spread tool (2025 product updates) targets emergency response with near-real-time visual intelligence: fireline intensity bands, rate-of-spread layers (including head rate of spread), and flame-length prediction up to 24 hours ahead aligned with USFS intensity/flame-length guidance for suppression strategy—explicit multi-hour-to-24h actionable lead times for crews and incident command.
   Source: OroraTech – Fire Spread feature updates blog (Sep 18, 2025)
   URL: https://ororatech.com/resources/news-blog/fire-spread-feature-updates-new-clarity-for-wildfire-response
33. OroraTech’s Wildfire Solution combines satellite thermal detection (alerts on the order of minutes) with predictive modeling to anticipate fire spread; Idaho became the first U.S. state to adopt the satellite-based system for real-time intelligence for firefighters, illustrating commercial delivery of detection-plus-spread forecasting to emergency services at operational (sub-daily) timescales.
   Source: OroraTech homepage / Fire Spread product messaging
   URL: https://ororatech.com/
34. UC San Diego’s WIFIRE Firemap operational decision-support tool allows users to set burn time in hours and generate rate-of-spread and flame-length outputs; the interface states that official fire perimeters are usually updated only once a day and satellite updates roughly every 6 hours—showing why agencies rely on multi-hour predictive spread models to fill large observation gaps between perimeter products.
   Source: WIFIRE Firemap (SDSC)
   URL: https://firemap.sdsc.edu/
35. During the January 2025 Los Angeles Palisades Fire, WIFIRE delivered the first predictive Firemap model to LA responders within minutes of the first smoke report; Firemap integrates weather, sensors, satellite imagery, and historical data, and FIRIS aerial IR perimeters then updated subsequent multi-run forecasts for evacuation and extended attack—demonstrating operational multi-lead-time perimeter forecasting from minutes of ignition through multi-day events (including NASA-supported expansion beyond a typical three-hour initial-response modeling window into 3–5 day extended attack).
   Source: UC San Diego Today – WIFIRE real-time wildfire response (Apr 6, 2025)
   URL: https://today.ucsd.edu/story/uc-san-diegos-wifire-program-provides-real-time-information-to-wildfire-responders
36. The Wildfire Interdisciplinary Research Center’s WRFx operational system runs coupled WRF-SFIRE fire–atmosphere forecasts for 48 hours twice daily (03z and 15z) during fire season, initializing from latest IR perimeters and satellite detections to provide expected fire behavior and air-quality impacts—an operational multi-horizon (through ~2 days) perimeter/spread forecast pipeline rather than a single next-day product.
   Source: Wildfire Interdisciplinary Research Center – Wildfire Information / WRFx
   URL: https://www.wildfirecenter.org/wildfire-information
37. Open-source ELMFIRE (Eulerian Level Set Model of FIRE spread), used in operational/utility contexts, is designed to forecast fire spread in real time, reconstruct historical fires, support initial attack and extended attack suppression modes, and run Monte Carlo ensembles—illustrating the industry standard architecture of short-horizon, re-initializable spread forecasts for emergency operations.
   Source: ELMFIRE official documentation site
   URL: https://elmfire.io/
38. NOAA Research (2025) describes the experimental Hourly Wildfire Potential Index as assessing wildfire potential updated every hour from model-predicted weather and as the first wildfire behavior model that refreshes every hour—evidence that even federal research ops are moving to hourly (not next-day-only) hazard/behavior products for decision support.
   Source: NOAA Research – Hourly Wildfire Potential Index article (Aug 28, 2025)
   URL: https://research.noaa.gov/an-experimental-noaa-tool-that-predicts-hourly-wildfire-hazards-across-the-u-s/
39. For the January 2025 Los Angeles wildfires, remote-sensing analysis found that within the first 24 hours after ignition the main fires burned about 75–80% of final fire area (including all affected residential areas), with Palisades Fire spreading through most Pacific Palisades residential areas in the first ~5 hours at maximum rates up to ~1.0–3.7 km/h—showing that a next-day-only perimeter/spread product arrives after the primary life-safety and structure-loss window and is therefore not fit for emergency-services sales use cases.
   Source: AGU Advances summary of LA 2025 fire spread/intensity study (snippet via publisher/search indexing of doi:10.1029/2025AV002064)
   URL: https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025AV002064
40. NIFC maps emphasize real-time fire perimeters updated daily and satellite-detected starts in near real time as the national operational map baseline—daily official perimeter cadence is too coarse alone for hour-scale tactics, which is why commercial/operational systems sell frequent re-forecasts of perimeter, ROS, and multi-hour (1–24 h) arrival surfaces for emergency services.
   Source: National Interagency Fire Center – Maps
   URL: https://www.nifc.gov/fire-information/maps
41. Next-day-only wildfire spread products are usually unsellable to emergency services because (1) initial attack requires minutes-to-hours intelligence on where the fire is and will be for resource deployment; (2) official observed perimeters are often only daily while satellites may update ~every 6 hours; (3) wind-driven WUI fires can destroy most residential exposure within ~5–24 hours; and (4) commercial buyers pay for under-30-second / seconds-scale re-simulations, 1-hour weather-driven ROS/flame-length surfaces, and 12–48 hour continuous forecast cycles that match shift planning and PSPS/evacuation timelines—capabilities next-day-only products do not deliver.
   Source: Synthesis of WIFIRE Firemap, UC San Diego WIFIRE operations report, Technosylva Wildfire Operations, and LA 2025 AGU fire-progression findings (URLs consulted above)
   URL: https://today.ucsd.edu/story/uc-san-diegos-wifire-program-provides-real-time-information-to-wildfire-responders
42. On the WildfireSpreadTS next-day spread benchmark, doubling historical training years (WSTS to WSTS+: 4 to 8 years, +66% fire events, +80% images) yields little or no accuracy gain for DNN spread models; authors attribute this to significant cross-year domain shift in p(x,y) and identify domain shift as a critical challenge for scaling data-driven wildfire modeling.
   Source: Lahrichi et al., Improved Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark (arXiv)
   URL: https://arxiv.org/html/2502.12003v3
43. Despite larger capacity (roughly 2x parameters), ResNet-50 U-Net, SwinUnet, and SegFormer often underperform a well-optimized ResNet-18 U-Net on leave-one-year-out WSTS evaluation; authors explicitly test whether rigorous year-held-out CV penalizes complex models via overfitting, finding the smaller model still wins under random CV as well—so scaling model capacity alone does not dominate gains.
   Source: Lahrichi et al., Improved Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark (arXiv)
   URL: https://arxiv.org/html/2502.12003v3
44. Increasing multi-source input feature volume is not always beneficial for next-day spread models: the full feature set (including weather forecasts) often underperforms vegetation-only or vegetation+topography sets; authors hypothesize low resolution and/or noise in weather forecast fields (27 km) versus fire masks (375 m) outweighs added explanatory power—a multi-source spatial/temporal alignment and scale mismatch failure.
   Source: Lahrichi et al., Improved Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark (arXiv)
   URL: https://arxiv.org/html/2502.12003v3
45. Spread models systematically struggle more on very small, newly ignited, or displaced fires than on larger consolidated fires, with performance positively correlated with fire size—failure modes concentrated where labeled positive pixels are scarcest rather than on well-developed multi-day fires.
   Source: Lahrichi et al., Improved Wildfire Spread Prediction with Time-Series Data and the WSTS+ Benchmark (arXiv)
   URL: https://arxiv.org/html/2502.12003v3
46. Despite sophisticated research, operational deployment of AI for wildfire management remains limited; dominant practical barriers cited include dataset imbalance and accessibility, inadequate evaluation metrics, prediction-format choices, and computational costs of large-scale models, which reduce trustworthiness and real-world applicability; a deployment checklist explicitly includes cost and latency.
   Source: Caron et al., AI for Wildfire Management: From Prediction to Detection, Simulation, and Impact Analysis (MDPI AI, 2025)
   URL: https://www.mdpi.com/2673-2688/6/10/253
47. Survey synthesis flags lack of generalization (models designed for specific environments fail to adapt across contexts), dataset restrictions, model biases from under-representation of real fire scenarios, and severe fire vs non-fire class imbalance due to wildfire rarity as recurring published and operational obstacles—not mere lab artifacts.
   Source: Caron et al., AI for Wildfire Management: From Prediction to Detection, Simulation, and Impact Analysis (MDPI AI, 2025)
   URL: https://www.mdpi.com/2673-2688/6/10/253
48. In wildfire danger forecasting framed from multi-source spatio-temporal cubes (Greece, daily 1 km), inherent stochastic label noise (NS3) is a major failure mode: high-risk samples are often labeled “low danger” simply because no fire occurred that day, especially summer negatives—noise that is input-dependent and cannot be fixed by collecting more unlabeled volume alone.
   Source: Kondylatos et al. / Prapas et al., Probabilistic machine learning for noisy labels in Earth observation (Scientific Reports, 2025)
   URL: https://www.nature.com/articles/s41598-025-19781-2
49. EO annotation pipelines also introduce information-loss noise from misalignment between inputs and labels (NS4: e.g., expert field masks poorly registered to satellite/SAR features), showing that multi-source volume without careful spatial-temporal co-registration injects systematic label noise that degrades supervised models.
   Source: Kondylatos et al. / Prapas et al., Probabilistic machine learning for noisy labels in Earth observation (Scientific Reports, 2025)
   URL: https://www.nature.com/articles/s41598-025-19781-2
50. A major challenge for AI wildfire spread models in operational-style settings is generalizing across regions with different terrain, vegetation, and climate; UB evaluation on Hawaii data vs Maui 2023 case study shows AI can complement but not yet fully replace physics-based FARSITE, while FARSITE fuel and structured inputs are labor-intensive and often significantly out of date—data freshness and domain transfer dominate over raw capacity.
   Source: University at Buffalo UBNow coverage of Hu et al. Natural Hazards study on DL wildfire spread vs FARSITE (2026)
   URL: https://www.buffalo.edu/ubnow/stories/2026/03/ai-wildfire-spread.html
51. Physics-based spread simulators (e.g., FARSITE, SPARK, Prometheus) offer detailed process fidelity but require extensive computation and environmental inputs that often limit real-time use; DL models improve runtime/scalability in data-rich settings but still fail at real-time high-resolution multimodal integration and remain mostly 2D, with scarce high-quality annotated fire samples due to rare, heterogeneous events.
   Source: Xu et al., Generative AI as a Pillar for Predicting 2D and 3D Wildfire Spread (arXiv)
   URL: https://arxiv.org/html/2506.02485v2
52. For multi-day multimodal spread forecasting (1–5 day horizon over large Russian regions), assembling high-quality multi-source training data is described as a core bottleneck; accuracy diminishes over longer lead times due to cumulative prediction error and environmental unpredictability; prevalence of small fires complicates training; using prior-day fire masks can bias models toward stagnant perimeters when fire extent is unchanged for several days.
   Source: Shadrin et al., Wildfire spreading prediction using multimodal data and deep neural network approach (Scientific Reports / PMC)
   URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10831103/
53. Multi-scale operational imaging constraints: early-stage fires are small, sparse, and easy for U-Net-style models to miss, while large fires produce image sizes that are expensive to process—driving two-stage resolution/tiling strategies; early-stage prediction remains harder than forecasting larger developed fires (F1 ~0.65 early vs ~0.75 large in the reported framework).
   Source: Newswise summary of multi-scale AI wildfire-spread tracking study (U-Net two-stage strategy)
   URL: https://www.newswise.com/articles/ai-tracks-wildfire-spread-across-scales
54. Review of remote sensing and ML for wildfire risk/detection/spread identifies major research gaps in cross-ecosystem generalization, real-time data integration, model optimization, and uncertainty quantification—indicating domain shift and operational data fusion, not just model capacity, dominate published limitation lists.
   Source: AIMS Environmental Science review: Artificial intelligence and remote sensing frameworks for wildfire (2026)
   URL: https://www.aimspress.com/article/doi/10.3934/environsci.2026004?viewType=HTML
55. Operational evaluation of data-driven fire-activity forecasting finds that standard ML test metrics can mislead deployment readiness: class imbalance and feature-space overlap between fire and no-fire samples limit metric relevance; region-wide daily inference is more diagnostic, and architectures that capture multi-timescale temporal structure (weather daily vs vegetation ~10-day) matter more than simply deeper CNNs for confident no-fire identification.
   Source: Operational evaluation of data-driven forest fire forecasting (arXiv HTML)
   URL: https://arxiv.org/html/2603.25469v2
56. Across published and operational wildfire AI settings, the dominant failure modes when scaling capacity or multi-source volume are (1) cross-year/region domain shift that prevents accuracy gains from more years of data, (2) severe class imbalance and inherent stochastic label noise (especially negatives), (3) multi-source spatial-resolution and temporal-alignment mismatches, and (4) compute/latency and data-freshness constraints for real-time use—rather than pure underfitting cured by larger architectures.
   Source: Synthesis of Lahrichi et al. (arXiv WSTS+), Caron et al. (MDPI AI 2025), and Kondylatos/Prapas et al. (Scientific Reports 2025)
   URL: https://arxiv.org/html/2502.12003v3
57. On the 2023 Maui wildfires, the physics-based FARSITE model achieved higher precision, lower recall, and a higher F1 score than top deep-learning models (ConvLSTM and ConvLSTM with attention) trained on Hawaiian wildfire data (2012–2023); the study concluded AI can complement but not yet fully replace established physics-based fire modeling tools.
   Source: University at Buffalo / UBNow (Hu et al. Natural Hazards study summary)
   URL: https://www.buffalo.edu/ubnow/stories/2026/03/ai-wildfire-spread.html
58. Deep learning models offered greater flexibility than FARSITE by adapting to diverse and more timely inputs (e.g., satellite imagery), whereas FARSITE depends on structured fuel and environmental inputs that are labor-intensive to produce and often outdated.
   Source: University at Buffalo / UBNow
   URL: https://www.buffalo.edu/ubnow/stories/2026/03/ai-wildfire-spread.html
59. Hybrid modeling approaches combining physics-based fire science with AI adaptability are highlighted as a path to better short-horizon (e.g., next 12–24 hour) perimeter forecasts for operational decision support.
   Source: University at Buffalo / UBNow
   URL: https://www.buffalo.edu/ubnow/stories/2026/03/ai-wildfire-spread.html
60. High-resolution physics-based wildland fire modeling has been much slower than real time and has not yet become operational for wildfire management; even research runs on small fires (~100 m²) on supercomputers must compromise spatial resolution.
   Source: USDA Forest Service Research and Development (Missoula Fire Lab / Finney et al. project)
   URL: https://research.fs.usda.gov/firelab/projects/deeplearning
61. A deep-learning surrogate of a high-resolution 1D physics fire-spread model reduced average per-case runtime from about 70 s (physics 1D model) to about 0.01 s (DL), while reproducing ROS, flame length, and flame-zone depth with mean absolute errors of about 0.078 m/s, 0.21 m, and 0.98 m on held-out test data.
   Source: USDA Forest Service Research and Development (Google Research collaboration)
   URL: https://research.fs.usda.gov/firelab/projects/deeplearning
62. USFS/Google Research aim to demonstrate a stand-alone DL surrogate as a substitution for the Rothermel fire-spread equation inside a 2D simulator such as FARSITE—an explicit physics-to-ML hybrid pathway for operational-scale perimeter/ROS forecasting.
   Source: USDA Forest Service Research and Development
   URL: https://research.fs.usda.gov/firelab/projects/deeplearning
63. Deep learning models (CNNs, RNNs, U-Net variants) often outperform traditional physics-based simulators in runtime, scalability, and—in data-rich environments—predictive accuracy by learning patterns from observations rather than explicit physical formulations.
   Source: arXiv position paper: Generative AI for Predicting 2D and 3D Wildfire Spread (Xu et al., 2025)
   URL: https://arxiv.org/html/2506.02485v1
64. Traditional deep learning fire models typically produce deterministic outputs, struggle with uncertainty quantification and long-range temporal dependency, remain largely 2D, and operate as black boxes with limited explainability—constraints that reduce trust for multi-horizon operational forecasting.
   Source: arXiv position paper: Generative AI for Predicting 2D and 3D Wildfire Spread (Xu et al., 2025)
   URL: https://arxiv.org/html/2506.02485v1
65. Quasi-empirical models such as Rothermel (and systems built on it, e.g., BEHAVE/FARSITE) are widely used in practice with moderate complexity; Prometheus is classified among mathematical/analogue wave-propagation tools used for spatial fire growth, while pure physical CFD models (FIRETEC, WFDS) offer high fidelity but high compute cost.
   Source: arXiv position paper: Generative AI for Predicting 2D and 3D Wildfire Spread (Xu et al., 2025)
   URL: https://arxiv.org/html/2506.02485v1
66. Cell2Fire (cellular-automata fire growth using Canadian FBP ROS) simulated wildfires up to about 30× faster than Prometheus with similar accuracy (reported above 90% accuracy / high agreement on fire scars), improving feasibility of multi-scenario and landscape-planning ensembles versus vector Huygens-type operational models.
   Source: Frontiers in Forests and Global Change: Cell2Fire (Pais et al., 2021)
   URL: https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2021.692706/full
67. A literature synthesis of fire-spread models found FARSITE (U.S., Rothermel/BEHAVE-based) and Prometheus (Canada, FBP-based Huygens wave model) to be the best-performing regional operational fire-growth simulators for historical fires in their respective domains.
   Source: Frontiers in Forests and Global Change: Cell2Fire (Pais et al., 2021)
   URL: https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2021.692706/full
68. Prometheus is a deterministic Canadian wildland fire growth simulation model developed for fire managers; it applies Huygens’ principle of wave propagation to rate-of-spread predictions from the Canadian Forest Fire Behavior Prediction (FBP) System using topography, fuel types, and weather.
   Source: Natural Resources Canada / Canadian Forest Service (Tymstra et al., Prometheus report; FRAMES catalog)
   URL: https://www.frames.gov/catalog/71310
69. WRF-SFIRE (and WRF-Fire) couples a mesoscale atmosphere model with a semi-empirical surface fire-spread model based on Rothermel’s rate-of-spread formula and level-set front propagation, capturing two-way fire–atmosphere feedback that pure offline ROS models and pure DL perimeter models typically omit.
   Source: UCAR/WRF User Guide (WRF-Fire documentation)
   URL: https://www2.mmm.ucar.edu/wrf/site/users_guide/fire.html
70. Coupled fire–atmosphere systems such as WRF-SFIRE carry a high computational burden that can impede operational forecast turnaround: example Pioneer Fire runs used 216 CPUs with ~2.7 h wall-clock per 48-h segment (~8.2 h for a 6-day run), and full chemistry coupling multiplies cost further.
   Source: Frontiers in Forests and Global Change: Integration of a Coupled Fire-Atmosphere Model (Kochanski et al., 2021)
   URL: https://www.frontiersin.org/journals/forests-and-global-change/articles/10.3389/ffgc.2021.728726/full
71. Computational resources are a major barrier to operational atmosphere–fire coupling: for high-resolution LES-type cases, required processor counts and wall times can exceed the fire’s lifetime, implying larger HPC infrastructure is needed for operational WRF-SFIRE use.
   Source: Nature Partner Journal / npj Natural Hazards-style report on WRF-SFIRE Bridger Foothills case (Cheung et al., 2025 abstract/page)
   URL: https://www.nature.com/articles/s44304-025-00132-0
72. For operational forecasting applications, atmospheric domain resolution for coupled WRF-Fire-type systems has been described as practically limited around ~400 m due to computational cost, constraining fine-scale multi-horizon perimeter detail relative to lighter empirical or DL approaches.
   Source: Geoscientific Model Development: Coupled atmosphere-wildland fire modeling with WRF-Fire (Mandel et al., 2011)
   URL: https://gmd.copernicus.org/articles/4/591/2011/gmd-4-591-2011.pdf
73. On the 2001 Dogrib Fire (Alberta), black-box optimization of Cell2Fire adjustment factors raised F1-score of predicted burn scar agreement from 0.74 (Prometheus baseline comparison context) to 0.83 versus real burn data, and Cell2Fire runtime scaled linearly while Prometheus runtime scaled exponentially—illustrating CA hybrid calibration advantages over pure vector physics growth models.
   Source: Scientific Reports PDF via Berkeley HumNet Lab (Kim et al., 2025; Cell2Fire optimization study)
   URL: http://humnetlab.berkeley.edu/wp-content/uploads/2025/07/s41598-025-05706-6.pdf
74. A hybrid ML rate-of-spread model (SVM-based) has been integrated inside WRF-SFIRE so ML RoS is evaluated at every pixel and time step like other RoS parameterizations—an operationally oriented hybrid path that keeps the coupled atmosphere–fire framework while replacing pure Rothermel RoS with data-driven RoS.
   Source: AMS Annual Meeting abstract: A Machine Learning Rate of Spread Model in WRF-SFIRE (Farguell et al., 2024)
   URL: https://ams.confex.com/ams/104ANNUAL/meetingapp.cgi/Paper/438753
75. An interpretable hybrid machine-learning fire model for western U.S. large-fire occurrence reported F1 ≈ 0.846, outperforming process-driven fire-danger indices by up to ~40% and common pure ML models by up to ~9%, while aligning fire–driver relationships more closely with established fire physics than black-box ML alternatives.
   Source: Earth's Future (Li et al., 2024) PDF via SILVIS/UW-Madison
   URL: https://silvis.forest.wisc.edu/wp-content/uploads/2024/12/Earth-s-Future-2024-Li-Projecting-Large-Fires-in-the-Western-US-With-an-Interpretable-and-Accurate-Hybrid-Machine.pdf
76. A multi-dimensional cellular automata model based on a simplified Rothermel formula reported area error rates of about 9.42%–15.63% and perimeter errors of about 4.21%–8.99% versus laboratory fire-spread observations, outperforming a simpler CA baseline—illustrating physics-parameterized CA skill on perimeter/area metrics.
   Source: CERNE / SciELO: Multi-dimensional Cellular Automata based on Rothermel (Zhang et al., 2021)
   URL: https://www.scielo.br/j/cerne/a/x8BskNTSh7MxkgzbzyY63Mg/?lang=en
77. Review literature on physics-based and ML wildfire-spread methods recommends hybrid approaches that combine ML pattern learning with physics-based representation of wind, terrain, and fuel to improve predictive capability and realism over either pure physics or pure data-driven models alone.
   Source: Journal of Forestry Research (Springer): Trending and emerging prospects of physics-based and ML wildfire models (Singh et al., 2024)
   URL: https://link.springer.com/article/10.1007/s11676-024-01783-x
78. FARSITE implements fire behavior models based on Rothermel (1972), while Prometheus implements Canadian FBP empirical spread models; both have been applied as operational-style spatial simulators internationally, reflecting entrenched agency adoption of semi-empirical physics/empirical growth tools over pure deep learning.
   Source: USDA Forest Service Treesearch PDF: Applying Fire Spread Simulators in New Zealand and Australia (Opperman et al.)
   URL: https://research.fs.usda.gov/download/treesearch/25947.pdf
79. Pure deep learning spread models remain limited in multi-horizon generalization across regions with different terrain, vegetation, and climate; even strong ConvLSTM results on Hawaii still trailed FARSITE’s balanced F1 on the Maui case study, reinforcing current operational preference for physics/empirical cores with AI as a complement.
   Source: University at Buffalo / UBNow
   URL: https://www.buffalo.edu/ubnow/stories/2026/03/ai-wildfire-spread.html
80. In multi-step forecasting theory, recursive (autoregressive) strategies typically win at short horizons for linear/stationary series because error accumulation is small and one model uses the full training set; direct multi-horizon models are preferred for long horizons and nonlinear learners (trees, neural nets) because they avoid compounded one-step error.
   Source: MetricGate — Recursive vs Direct Multi-Step Forecasting
   URL: https://metricgate.com/blogs/recursive-vs-direct-multistep-forecasting/
81. Recursive multi-step forecasts often match direct forecasts over the first few horizons but degrade at longer horizons due to error accumulation (especially with nonlinear models); direct forecasts avoid propagation bias but incur higher variance when training data are limited.
   Source: Taieb & Hyndman — Recursive and direct multi-step forecasting: the best of both worlds (rectify paper summary via Stratify arXiv)
   URL: https://arxiv.org/html/2412.20510v1
82. Classical multi-step forecasting analysis frames recursive/autoregressive rollouts as high-bias (error compounds with each step) and direct multi-horizon heads as high-variance (separate model per horizon; no error feedback); no single strategy dominates all horizons and model classes.
   Source: Green et al. — Stratify: Unifying Multi-Step Forecasting Strategies (arXiv)
   URL: https://arxiv.org/html/2412.20510v1
83. For time-resolved wildfire spread on 15-minute increments, an EPD-ConvLSTM autoregressive rollout remained stable and realistic after 100 iterative steps (>24 hours of simulated fire), with Jaccard scores 0.89–0.94 on the final scar; a single-step multi-hour head (DCIGN) failed to produce realistic rollouts beyond about 10 autoregressive steps.
   Source: Burge et al. — Recurrent Convolutional Deep Neural Networks for Modeling Time-resolved Wildfire Spread Behavior (arXiv:2210.16411)
   URL: https://arxiv.org/pdf/2210.16411
84. Burge et al. argue single 6- or 24-hour multi-horizon DNN predictions lack temporal resolution needed for active fire interventions; minute-scale autoregressive rollouts (Δτ = 15 min) are required when operational decisions need intermediate fire-state updates rather than only a final burned area.
   Source: Burge et al. — Recurrent Convolutional DNNs for Time-resolved Wildfire Spread (arXiv:2210.16411)
   URL: https://arxiv.org/pdf/2210.16411
85. At satellite/regional scale with ~1-day steps, a multi-horizon direct approach (separate MA-Net trained per day for horizons 1–5 days) achieved F1 from 0.68 (day 1) to 0.65 (day 5); authors chose 1–5 day horizons to match high-resolution meteorological data availability and note accuracy diminishes over longer periods due to cumulative prediction error.
   Source: Shadrin et al. — Wildfire spreading prediction using multimodal data and deep neural network approach (Scientific Reports / PMC)
   URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10831103/
86. Shadrin et al. contrast UAV data as suited to short-term/small-scale fire monitoring versus satellite multimodal data as preferable for multi-day, large-scale spread forecasts (their setting used ~650 m cells and separate per-horizon models).
   Source: Shadrin et al. — Wildfire spreading prediction using multimodal data (Scientific Reports / PMC)
   URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC10831103/
87. WildfireSpreadTS targets active-fire spread prediction at 24-hour temporal resolution using multi-modal remote sensing—matching the coarser cadence of many polar-orbiting satellite products rather than minute-scale ground or drone streams.
   Source: Gerard et al. — WildfireSpreadTS (NeurIPS 2023 poster / OpenReview)
   URL: https://neurips.cc/virtual/2023/poster/73593
88. NASA FIRMS ultra real-time (URT) MODIS/VIIRS active-fire products can reach ~25 s (MODIS) and ~50 s (VIIRS) latency from observation via direct broadcast—showing that some satellite detections can be near real-time even when full-scene revisit remains hours to days.
   Source: NASA Earthdata — FIRMS Adds Ultra Real-Time Data from MODIS and VIIRS
   URL: https://www.earthdata.nasa.gov/news/feature-articles/firms-adds-ultra-real-time-data-from-modis-viirs
89. Geostationary imagers (e.g., Himawari-8 AHI) provide wildfire-relevant updates at ~2.5–10 minute temporal resolution, whereas polar LEO sensors often revisit on scales of hours to days (e.g., MODIS 1–2 days; high-resolution optical like Sentinel-2 ~5 days), constraining the natural step size of satellite multi-horizon heads.
   Source: Zhang et al. — Real-Time Wildfire Detection Algorithm Based on VIIRS… / Himawari-8 discussion (MDPI Remote Sensing)
   URL: https://www.mdpi.com/2072-4292/15/6/1541
90. LEO satellite revisit intervals of hours to days delay early detection relative to continuous platforms; GEO updates ~every 10 minutes still incur processing/alert latencies often tens of minutes to hours, limiting how fine an autoregressive step can be if only satellite inputs are available without future weather/fire-state observations.
   Source: EXCI — How to Overcome Satellites Limitations in Early Wildfire Detection
   URL: https://www.exci.ai/real-time-satellites-limitations/
91. Ground IoT wildfire systems can deliver sensor-to-center communication delays of a few minutes and commercial deployments claim ignition detection in ~5 minutes (e.g., N5 Sensors) or under an hour (e.g., Dryad)—supporting minute-scale sequential updating more naturally than daily satellite multi-horizon heads.
   Source: Chan et al. — A Survey on IoT Ground Sensing Systems for Early Wildfire Detection (arXiv)
   URL: https://arxiv.org/html/2312.10919v2
92. UAVs/drones provide high spatial resolution and flexible revisit for local active-fire monitoring but require deployment authorization and cannot match satellite large-area continuous coverage; literature positions them as complements for short-range confirmation and real-time front mapping rather than multi-day regional multi-horizon forecasting.
   Source: Chan et al. — IoT Ground Sensing Systems for Early Wildfire Detection (arXiv survey)
   URL: https://arxiv.org/html/2312.10919v2
93. MIMO/multi-horizon neural heads (one model outputting the full horizon vector) avoid recursive error propagation while sharing parameters across horizons and dominate many deep-learning forecasting benchmarks—relevant when satellite weather/fire masks update only daily and intermediate states cannot be re-observed for AR feedback.
   Source: MetricGate — Recursive vs Direct Multi-Step Forecasting (MIMO discussion)
   URL: https://metricgate.com/blogs/recursive-vs-direct-multistep-forecasting/
94. In simulated high-frequency wildfire settings, autoregressive ConvLSTM-style models are reported to maintain stability beyond 24 h when rolled out at 15-minute increments (EDP-ConvLSTM cited as employing autoregressive recurrent forecasting at 15-min steps with iterative rollout stability >24 h).
   Source: Andrianarivony et al. — A Modality-Aware Ensemble-of-Experts Model for Wildfire Spread (MDPI Remote Sensing, citing EDP-ConvLSTM)
   URL: https://www.mdpi.com/2072-4292/18/9/1416
95. OroraTech commercially separates Burnt Area (post-fire automated satellite mapping of burned extent/severity at ~20 m, delivered in 2–3 days for recovery, civil protection, and damage assessment) from Fire Spread (near-instant Rothermel/ForeFire/WindNinja-based spread predictions over 1–24 h, GeoJSON/KML export for tactical field response). Both are sold as distinct SKUs within one Wildfire Solution platform and are marketed to civil protection and emergency operations.
   Source: OroraTech Burnt Area product page; OroraTech Fire Spread product page
   URL: https://ororatech.com/all-products/burnt-area
96. OroraTech’s peer-facing EGU description documents a lifecycle dual-product architecture: during-fire operational support uses detections to update dynamic fire-spread simulations for tactical decisions (fire-break placement, resource allocation), while after containment a separate burned-area mapping product supports impact assessment, reporting, and recovery—pre-, during-, and post-fire products kept coherent but functionally separate.
   Source: EGU General Assembly 2026 abstract EGU26-3365 (OroraTech GmbH)
   URL: https://meetingorganizer.copernicus.org/EGU26/EGU26-3365.html?pdf
97. OroraTech Fire Spread is explicitly field-ops oriented: seconds-scale simulations from ignition points/fire clusters, adjustable wind/fuel moisture, time-stepped geometry animations, and civil-protection use cases for resource allocation; it is sold separately from the lab/post-fire Burnt Area mask product.
   Source: OroraTech Fire Spread product page
   URL: https://ororatech.com/all-products/fire-spread
98. EFFIS (Copernicus Emergency Management) implements a dedicated Rapid Damage Assessment burned-area product (MODIS/Sentinel-2 perimeter mapping, ~30 ha historically, refined to smaller fires; ~95% of EU burned area) that is operationally separate from fire-danger forecasting and active-fire monitoring modules used by European civil protection.
   Source: EFFIS Technical Background – Rapid Damage Assessment (European Commission JRC)
   URL: https://forest-fire.emergency.copernicus.eu/about-effis/technical-background/rapid-damage-assessment
99. Copernicus LAC documents an explicit multi-service architecture for emergency wildfire support: Burned Area Mapping (BAM) and Burned Area Severity (BAS) as post/active mask products from optical TIR/NIR/SWIR, versus Fire Danger Mapping (FDM) for ignition/propagation risk—separate services across pre-, ongoing, and post-fire phases under CEMS/EFFIS/GWIS.
   Source: CopernicusLAC Platform – Wildfire services documentation
   URL: https://docs.copernicuslac.terradue.com/services/fire/intro/
100. Technosylva’s commercial platform sold to fire agencies and utilities splits Planning (historical/climatology fire simulations, asset risk, mitigation prioritization) from Operations (real-time fire behavior modeling, resourcing, PSPS, situational awareness with fire-spread predictions)—a dual product line rather than a single monolithic lab model.
   Source: Technosylva Wildfire & Flood Risk Intelligence Platform overview
   URL: https://technosylva.com/products/overview/
101. A 2023 International Journal of Wildland Fire study co-led by Technosylva and CAL FIRE validated operational fire-spread (ROS) models on 1,853 California wildfires using independent FireGuard progression polygons every 15 min; the study treats observed burned-area growth as validation truth and operational ROS simulators (e.g., WFA-e/Rothermel) as the field product, concluding models are accurate enough for real-time initial-attack use despite biases.
   Source: Technosylva summary of Cardil et al. IJWF operational ROS validation; study link
   URL: https://technosylva.com/a-first-time-validation-of-fire-spread-modeling-on-the-fire-line/
102. Peer-reviewed operational modeling literature states full-physics CFD fire models are unsuitable for wildfire emergency situations, while operational fire-spread simulators (semi-empirical ROS/front geometry, e.g., Rothermel + Huygens/FARSITE lineage) are the field-deployable product; satellite/final burned scar and observed perimeters are treated as independent reference/validation data, not the same product as the ROS forecast.
   Source: Frontiers in Mechanical Engineering – Rios et al. (2019), Data-Driven Fire Spread Simulator
   URL: https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2019.00008/full
103. Remote-sensing literature formalizes product independence: active-fire products (hotspots at overpass) versus burned-area products (spectral change masks such as MODIS MCD64A1) are designed as separate pipelines; active-fire observations can be treated as independent of burned-area products used for burn-patch extraction, enabling downstream ROS/geometry estimation without coupling the lab mask model to the field spread model.
   Source: International Journal of Remote Sensing – Humber et al. (2022), remote sensing approach to fire rate of spread
   URL: https://www.tandfonline.com/doi/full/10.1080/01431161.2022.2027544
104. NIST LOFM workshop synthesis classifies operational models as mostly empirical rate-of-spread models that run much faster than real time with simple interfaces for decision frameworks (e.g., WFDSS), while research/high-fidelity models target burn-scar physics; incident commanders need faster-than-real-time fire-spread information for evacuation and suppression—evidence for selling a field ROS/geometry product distinct from lab burned-area/mask research models.
   Source: NIST Special Publication 1245 – Large Outdoor Fire Modeling (LOFM) Workshop Summary Report (search/citation corpus)
   URL: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1245.pdf

---

## Verification stats

- Claims survived: **104**
- Dropped: **2** (`{'duplicates': 0, 'refuted': 2, 'verifierFailed': 0}`)
- Subqueries: 7

---

## Local WFD application (2026-08-06) — impact + PR expansion

Synthesis failed at research time (`ENAMETOOLONG`); this section is the **applied** conclusion for WildfireFrontDynamics after MultiHorizon PR1–PR4.

### Did multihorizon improve our results?

**No on metrics. Yes on product surface.**

| Gate / metric | Status after PR1–PR4 |
|---------------|----------------------|
| Lab U1 honest IoU ~0.857 | Unchanged (no retrain) |
| Tobarra KEEP/KILL | Still **KILL** (K1 lift &lt; 0) |
| Kaggle NDWS v21 IoU ~0.22 | Unchanged |
| GO_MES | Still false (O1/O2 external) |
| Multi-horizon 1/3/5/12/24 h field_ops API | **New** (isotropic v1) |
| Tobarra multipass geometry ROS → envelope | Attachable (~6.14 m/min → 368 m @ 1 h) |

Full audit: `docs/MULTIHORIZON_IMPACT_AUDIT_20260806.md` (+ JSON twin).

### Research → WFD decision (dual stack)

| Research finding | WFD action |
|------------------|------------|
| Next-day-only unsellable to emergency services (41, 39) | Keep **field_ops multihorizon** as SKU separate from lab mask |
| OroraTech/Technosylva dual product (95–100) | Lab `ml_product_go` ≠ field fusion; fusion stays OFF |
| Larger U-Nets/ViTs do not win LOYO (3, 8, 43) | **Do not** bet next sprint on bigger U-Net (PR11 kill-by-default) |
| Ops skill = Rothermel/hybrid re-sim + re-init (26–37, 57–79, 101) | Wave B: anisotropic + hybrid + re-init + multipass **validation** (PR5–PR10) |
| Isotropic buffer alone is not validated tactical skill | Only claim “better results” after **PR8** multipass scorecard |
| Domain shift kills more data years (13, 42) | Prefer LOFO honesty over silent year stacking |

### Expanded PR plan

See **`docs/design/PR_PLAN_MULTIHORIZON_FIELDOPS.md`**:

- Wave A PR1–4 **done** (isotropic API)
- Wave B PR5–13: sector anisotropic → S4 re-export → hybrid envelope → multipass validate → re-init → GeoJSON → optional lab lightweight → operator surface → wind stack
- Wave C kill list: larger U-Net as field product, IoU-as-ROS, KEEP/ECE thrash reopen

**Sprint order:** PR6 → PR5 → PR8 → PR7/9/10 → PR12 → PR13; PR11 only if lab experiment justified.
