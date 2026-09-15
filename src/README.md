# Source Code Overview

Welcome to the `src/` directory of the Unified ATC Terminal Safety System. This document serves as a comprehensive guide for new developers joining the project to quickly understand the architecture, folder structure, and how to work with the codebase.

## 🏗️ Architecture at a Glance

The system is a real-time Air Traffic Control (ATC) safety monitor focused on a specific terminal zone (currently DEL - VIDP). It ingests ADS-B flight telemetry and weather data, runs kinematic collision detection algorithms, and streams the results to a React-based frontend dashboard via WebSockets.

The `src/` directory is split into two independent but cooperating applications:
- **`backend/`**: A Python FastAPI server handling data ingestion, business logic, safety calculations, and WebSocket broadcasting.
- **`frontend/`**: A React Single Page Application (SPA) built with Vite, rendering the real-time map, telemetry data, and safety alerts.

---

## 📂 Directory Structure

### `backend/` (Python FastAPI)

The backend is strictly typed and built for performance, utilizing asynchronous I/O (`asyncio`) to ensure smooth telemetry broadcasting without blocking.

*   **`main.py`**: The application entry point. It sets up the FastAPI app, manages the WebSocket pool (`/ws/telemetry`), and controls the background polling tasks (via FastAPI's `lifespan` context).
*   **`config/`**:
    *   `settings.py`: Configuration management using `pydantic-settings`. Loads environment variables.
    *   `airports.json`: Definitions of monitored airports (e.g., bounding boxes, runway details, center coordinates).
*   **`services/`**:
    *   `opensky_service.py`: Connects to the OpenSky Network API to fetch real-time ADS-B aircraft data. Implements caching and mock fallback logic.
    *   `weather_service.py`: Fetches weather data from OpenWeatherMap, applying aggressive caching to respect API limits.
*   **`engine/`**:
    *   `collision_engine.py`: The core kinematic collision engine. Analyzes aircraft trajectories, altitudes, and speeds in real-time to detect potential conflicts and generate alerts.
*   **`requirements.txt`**: Standard Python dependencies (`fastapi`, `uvicorn`, `httpx`, `pydantic`).

### `frontend/` (React + Vite)

The frontend is a fast, modern dashboard tailored for displaying high-frequency data streams.

*   **`src/`**: The core React application source.
    *   **`components/`**: Reusable UI elements (maps, alert lists, telemetry dashboards, etc.). Uses `lucide-react` for icons and `recharts` for data visualization.
    *   **`hooks/`**: Custom React hooks (e.g., for managing WebSocket connections and telemetry state).
    *   `App.jsx`, `main.jsx`: React entry points assembling the components.
    *   `App.css`, `index.css`: Styling files heavily leveraging **Tailwind CSS**.
*   **`package.json`**: NPM dependencies and scripts (Vite, React Leaflet, Framer Motion, Tailwind).

---

## 🔄 Data Flow

1.  **Ingestion (Backend):**
    *   The `OpenSkyPoller` fetches ADS-B data every 120 seconds.
    *   The `WeatherService` fetches METAR/weather data, caching it for 300 seconds.
2.  **Processing (Backend):**
    *   Every 2 seconds, the `CollisionEngine` evaluates the current aircraft snapshot against the weather and airport boundaries to find safety breaches.
3.  **Streaming (Backend ➔ Frontend):**
    *   The backend broadcasts a unified JSON payload to all connected clients over the `/ws/telemetry` WebSocket endpoint. This is done from cache, preventing API rate-limit exhaustion.
4.  **Rendering (Frontend):**
    *   The React frontend receives the WebSocket payload and updates the state.
    *   Aircraft positions are updated on a live map (via `react-leaflet`), and alerts are animated into the UI (via `framer-motion`).

---