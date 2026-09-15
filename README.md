# 🚀 ATC OMNI-ZONE TERMINAL SAFETY SYSTEM

---

## 👥 Team

| Field | Value |
|---|---|
| **Team Name** | Code Crusaders |
| **Track** | Open |
| **Team Lead** | FAIZAN SAIYED — 24dcs112@charusat.edu.in |
| **Members** | HARSHRAJ PUNVAR, HET SAGAR, MANAN SHAH |

---

## 🎯 Problem Statement

Air traffic controllers must manually predict future positions of aircraft in
crowded terminal airspace while also monitoring runway traffic, creating a high
cognitive workload and increasing the risk of mid-air collisions and runway incursions.

---

## 💡 Solution

We built a real-time ATC safety dashboard that ingests ADS-B telemetry and
weather data, predicts airborne and ground conflicts with a physics-based
engine, and streams actionable alerts to a React tactical map.

---

## ✨ Key Features

- **Feature 1:** "60-second airborne time-to-closest-approach detection using cylindrical separation thresholds"
- **Feature 2:** "Weather-aware ground stopping-distance envelopes and runway incursion detection"
- **Feature 3:** "Real-time WebSocket telemetry streaming with cached 2-second broadcasts"
- **Feature 4:** "React-Leaflet tactical map with 50 km geofence, runway geometry, trajectories, and P-E-R aircraft highlighting"
- **Feature 5:** "Resolution advisories, countdown timers, aircraft search, and detailed telemetry inspection"

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| **Languages** | Python, JavaScript |
| **Frameworks** | FastAPI, React, Vite, React-Leaflet |
| **IBM Technologies** | IBM Bob |
| **Databases** |  |
| **Other** |  |

---

## 📁 Repository Structure

```
├── src/                  # All source code
├── docs/                 # Written documentation
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   └── setup-guide.md
├── demo/                 # Demo artifacts
│   ├── screenshots/      # App screenshots
│   └── demo-video-link.txt  # Link to demo video
├── presentation/         # Slide deck
└── submission.yaml       # Structured submission metadata
```

---

## ⚡ How to Run

> **Copy these exact steps from your [`docs/setup-guide.md`](docs/setup-guide.md)**

```bash
# 1. Clone the repo
git clone https://github.com/[your-repo].git
cd [your-repo]

# 2. Install dependencies
[your install command here]

# 3. Configure environment
cp .env.example .env
# Edit .env with your values

# 4. Run the project
[your run command here]
```

---

## 🖥️ Demo

| Artifact | Link |
|---|---|
| 📹 Demo Video | [See demo/demo-video-link.txt](demo/demo-video-link.txt) |
| 🌐 Live Demo | [See demo/live-demo-url.txt](demo/live-demo-url.txt) |
| 🖼️ Screenshots | [See demo/screenshots/](demo/screenshots/) |
| 📊 Presentation | [See presentation/slides.pdf](presentation/) |

---

## ⚠️ Known Limitations

> Be honest — judges appreciate transparency over overclaiming.

The system currently monitors DEL through a fixed WebSocket route and uses
JSON airport configuration with in-memory caching instead of PostgreSQL/PostGIS.
It depends on OpenSky Network and OpenWeatherMap APIs, which have daily limits,
so ADS-B data is fetched every 120 seconds and weather is cached for 300 seconds.
If credentials are unavailable or APIs are temporarily unavailable, deterministic
mock aircraft and default weather are used. The prediction model is linear and
does not yet include pilot response, ATC constraints, terrain, or advanced
operational-grade weather modeling.

---

## 🏅 What We're Most Proud Of

The strongest part of the project is the pure-mathematics collision engine.
It separates horizontal and vertical airborne safety checks, models realistic
forward stopping envelopes for ground traffic, uses runway line-segment
geometry, and produces actionable resolution advisories rather than generic
warnings.

---
