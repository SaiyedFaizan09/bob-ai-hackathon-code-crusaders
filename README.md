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

Before you begin, ensure you have the following installed:

- [Python 3.11+]
- [Node.js 18+]

### Obtain API Keys (Free)

The system relies on two external APIs. **If you skip this step, the system will automatically fall back to an offline mock data generator, and all UI features will still work.**
1. **OpenSky Network:** Sign up at [OpenSky Network](https://opensky-network.org/my-opensky/account) to obtain your `Client ID` and `Client Secret` (OAuth2 Credentials).
2. **OpenWeatherMap:** Sign up at [OpenWeatherMap](https://home.openweathermap.org/api_keys) and generate an `API Key`.

### Environment Variables

1. Navigate to the `src` folder in the project.
2. Duplicate/copy the `.env.example` file and rename the new file to `.env`.
3. Open `src/.env` in a text editor and fill in your newly generated API keys:
```bash
OPENSKY_CLIENT_ID="your_real_client_id"
OPENSKY_CLIENT_SECRET="your_real_client_secret"
OPENWEATHER_API_KEY="your_real_api_key"
```
### Installation

```bash
# 1. Clone the repository
git clone https://github.com/[your-org]/[your-repo].git
cd [your-repo]
```
### Set up the Backend

Open a terminal and run the following commands to configure and start the backend:

```bash
# 1. Navigate to the backend directory
cd src/backend

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate the virtual environment (Windows)
.venv\Scripts\activate
# (Note: For macOS/Linux, use: source .venv/bin/activate)

# 4. Install backend dependencies
pip install -r requirements.txt

# 5. Start the backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
**Verify it works:** Open http://localhost:8000/health in your browser. You should see a JSON status response indicating the system is healthy.

### Set up the Frontend

Open a new, separate terminal window (leave the backend terminal running in the background) and run the following commands:
```bash
# 1. Navigate to the frontend directory
cd src/frontend

# Copy the example environment file to create your own .env file
cp .env.example .env

# 2. Install frontend dependencies
npm install

# 3. Start the frontend development server
npm run dev
```
### Access the Dashboard

Open your web browser and navigate to: http://localhost:3000

The system will automatically establish a WebSocket connection with the backend, load the dark-mode ATC Tactical Display, and begin streaming live airborne telemetry!

### Troubleshooting

| Issue | Solution |
|---|---|
| `Virtual environment fails to activate` | On macOS or Linux, ensure you are using source .venv/bin/activate instead of the .venv\\Scripts\\activate command intended for Windows. |
| `Missing live data on the UI` | Ensure you have correctly registered at OpenSky Network and OpenWeatherMap, and that your API keys are placed in src/.env. If missing, the app safely falls back to a mock data generator and all UI features will still work. |

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
