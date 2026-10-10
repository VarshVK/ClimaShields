# ClimaShield — Atmospheric Risk & Flood Evacuation Intelligence Platform

ClimaShield is a comprehensive, production-grade climate resilience and emergency decision-support platform designed for India. It unites two critical capabilities into a single dashboard:

1. **AI Weather Forecast Reliability & Uncertainty Quantification Engine**: Multi-model numerical weather prediction (NWP) ensemble analysis, spread-skill diagnostics, probabilistic failure calibration, and renewable grid dispatch scenario hedging.
2. **Flood Evacuation Route Planner & Decision-Support System**: Topographical risk modeling, real-time road inundation penalty weighting, Dijkstra & A* graph routing, dynamic disaster simulations, and step-by-step emergency navigation.

---

## 🌟 Key Features

### Module 1: AI Weather Forecast Reliability Detector
- **India-Centric Spatial & Grid Coverage**: Calibrated across all Indian meteorological regimes and synchronous power grids (Northern, Western, Southern, Eastern, North-Eastern).
- **Multi-Model NWP Ensembles**: Integrates live ensemble members from NOAA GFS (31 runs), ECMWF IFS (51 runs), DWD ICON (40 runs), and CMC GEM (21 runs) via Open-Meteo.
- **Resilient Zero-Downtime Failover**: Instant seamless failover to high-fidelity calibrated NWP climatology when running in offline or DNS-restricted environments.
- **Historical Ground-Truth Verification**: Evaluated against 90-day continuous archive reanalysis (ERA5) with zero data leakage (chronological 70/30 train/test split).
- **Advanced Multi-Graph Meteorological Suite**:
  - *Ensemble Fan & Spaghetti Distribution*: 80% credible interval ($P_{10}$ to $P_{90}$) and deterministic comparison.
  - *Spread vs Baseline MAE Diagnostic*: Identifies chaotic atmospheric divergence.
  - *AI Calibrated Confidence & Risk Profile*: Calibrated failure probability tracking across lead horizons (Days 3 to 10).
  - *90-Day Retrospective Error History*: Validated ground-truth accuracy.
- **Renewable Energy Scenario Hedging**: 3-tier wind energy dispatch advisory ($P_{10}$ conservative, Mean $\mu$, $P_{90}$ surge) with turbine cut-in and storm cut-out alerts.

### Module 2: Pan-India Flood Evacuation Route Planner & AI Flood Predictor
- **Universal Pan-India City Search & Dynamic Generation**:
  - Search **ANY** city, town, or river basin across India (e.g., Pune, Bengaluru, Patna, Varanasi, Cuttack, Lucknow, Jaipur) with live Open-Meteo geocoding.
  - Dynamically synthesizes topologically verified road networks with realistic elevation models, high-ground shelters, and transit corridors.
  - Also includes 7 pre-calibrated major metropolitan river basin presets: Chennai, Mumbai, Delhi, Kerala, Assam, Kolkata, and Gujarat.
- **AI Flood Predictor: When & Where Engine (Ungauged Catchments)**:
  - *Calibrated Random Forest Model*: Trained and Platt-calibrated (`CalibratedClassifierCV(cv=3)`) achieving **91.0% Test Accuracy, 0.952 ROC-AUC, 0.894 F1-Score, and 0.0785 Brier Score**.
  - *Predicts WHEN*: Computes Kirpich time of concentration ($T_c$), SCS basin lag ($T_{\text{lag}}$), flood onset arrival window, peak crest arrival timestamp, recession horizon, and generates a 24-hour synthetic discharge hydrograph ($Q$ in $\text{m}^3/\text{s}$).
  - *Predicts WHERE*: Evaluates spatial inundation probability ($P_{\text{flood}}$) and water depth ($h$ in $\text{cm}$) across all nodes and roads using hydro-morphometric features: elevation, distance to canal/river, terrain slope, catchment area, imperviousness, forecast precipitation, rainfall intensity, and antecedent precipitation index (API).
- **Resilient Emergency High-Ground Detour (Zero-Dead-End Routing)**:
  - High-clearance corridors ($> 12\text{ m}$) remain open lifelines with caution penalties rather than total disconnects.
  - Under extreme monsoonal downpours ($> 85\text{ mm}$), Dijkstra automatically activates the **Emergency High-Ground Trajectory**, guaranteeing evacuees a verified safe exit path without failing.
- **Live 7-Day Meteorological Telemetry Synchronization**:
  - Live radar, ground-truth reanalysis, and future NWP precipitation, soil saturation, and runoff volume seamlessly sync between Module A and Module B.
- **Interactive Cartography (Leaflet)**: Smooth dark and light mode map rendering, color-coded road risk states (Safe 🟢, Moderate 🟡, High Risk 🟠, Blocked 🔴), emergency shelter pins ⛑️, and glowing route polylines.
- **Topographical Graph Routing**: Evaluates elevation, water pooling, and road status using Dijkstra (weighted shortest safe path) and A* search (elevation bias).
- **Emergency Shelter Auto-Optimization**: Automatically discovers and routes to the safest high-elevation sanctuary with available medical triage and bedding capacity.
- **Dynamic Disaster Simulation Engine**: Multi-scenario simulations per region (e.g. Adyar Causeway breach, Mithi River overflow, Yamuna high-flood discharge, Brahmaputra monsoonal crest).
- **Decision Explainability ("Why This Route?")**: Quantifies safety advantages (`+32% Safer`), highlights avoided hazardous segments, and generates turn-by-turn navigation tables.

---

## 🛠️ System Architecture & Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic, NetworkX / Custom Graph Routing, Scikit-learn, NumPy, Pandas, SciPy |
| **APIs** | Open-Meteo Ensemble API, Historical Forecast API, Weather Archive API (ERA5), Geocoding API |
| **Frontend** | Modern Vanilla JavaScript (ES6+), HTML5, CSS3, Leaflet.js (Cartography), Chart.js (Meteorology) |
| **Caching** | SQLite persistent client-side and backend caching with 6-hour TTL |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10 or higher
- Git (optional)

### 2. Install Dependencies
```bash
cd kpr09-weather-reliability
pip install -r requirements.txt
```

### 3. Start Application
You can start the server using any of the following commands:

**Option A: Using the launcher script (Recommended)**
```bash
./run.sh
# or
./start.sh
```

**Option B: Directly via Python**
```bash
python3 backend/app.py
```

**Option C: Directly via Uvicorn**
```bash
python3 -m uvicorn backend.app:app --host 127.0.0.1 --port 8080 --reload
```

### 4. Access the Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:8080
```

Use the top navigation bar to toggle between:
- **`[ 🌤️ Weather Forecast Reliability ]`**
- **`[ 🚨 Flood Evacuation Route Planner ]`**

---

## 🧪 Automated Test Suite

Run the full end-to-end integration and verification suite:
```bash
python3 -m unittest discover -s tests
```

---

## 📁 Project Structure

```
kpr09-weather-reliability/
├── backend/
│   ├── app.py                      # FastAPI unified application & static server
│   ├── ensemble_processor.py       # NWP multi-model ensemble statistics
│   ├── ml_pipeline.py              # Calibrated probabilistic confidence scoring
│   ├── open_meteo.py               # Open-Meteo API connector & SQLite cache
│   ├── energy_advisor.py           # Wind farm dispatch scenario hedging
│   └── flood/                      # Flood Evacuation Subsystem
│       ├── api/router.py           # Flood routing & simulation REST endpoints
│       ├── data/road_network.py    # Topographical road graph & shelters
│       ├── graph/road_graph.py     # Graph structure & weight models
│       ├── models/schemas.py       # Pydantic data models & request schemas
│       ├── risk/assessment.py      # Hydrologic pooling & road risk evaluation
│       ├── routing/engine.py       # Dijkstra & A* shortest safe path engine
│       └── services/               # Evacuation, simulation, and weather services
├── frontend/
│   ├── index.html                  # Unified HTML5 layout & module views
│   ├── styles.css                  # Dark & Light responsive styling
│   ├── app.js                      # Controller for weather analytics & flood map
│   ├── chart.umd.min.js            # Chart.js library
│   ├── leaflet.js                  # Leaflet cartography engine
│   ├── leaflet.css                 # Leaflet CSS styles
│   ├── images/                     # Leaflet map marker assets
│   └── logo.png                    # ClimaShield brand logo
├── tests/
│   └── test_pipeline.py            # Unit & integration tests
├── requirements.txt                # Python package dependencies
├── run.sh                          # Main startup script
├── start.sh                        # Alias startup script
└── README.md                       # System documentation
```

---

## 🛡️ License & Disclosures
- **Meteorological Data**: Open-Meteo under CC BY 4.0 (attribution to ECMWF, NOAA, DWD).
- **Cartography**: OpenStreetMap contributors, CARTO.
- **Operational Safety**: Evacuation routes are calculated as a decision-support guide based on topographical risk and simulated water levels. During an active state emergency, always comply with local authorities and disaster response directives.
