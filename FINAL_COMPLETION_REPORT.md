# Final Completion Pass

## Added
- Live Leaflet network map backed by `/api/network` with canonical hub coordinates and directed network edges.
- Route history (last 20 runs) persisted locally in the browser.
- CSV audit export for generated route personas, ETA, cost, threat, p85 delay, scenario delay, and route legs.
- Visible route-disruption alert when a selected scenario still affects a recommended option.
- Backend route-network payload now exposes latitude/longitude for map rendering.
- Basic automated regression tests for scenario mode/delay and directed network integrity.

## Previously fixed
- p85 quantile model wired into live routing.
- Canonical location encoding adapter.
- Scenario mode isolation and Suez bypass behavior.
- CARF/NLP routing integration.
- Routing-policy and transport-preference edge cases.
- Frontend/API request synchronization and error handling.
- Windows dependency/startup compatibility.

## Final local verification
- Backend starts successfully on Windows.
- NLP model loads successfully.
- Frontend Vite server starts successfully.
- SUEZ_BLOCK scenario was exercised through the dashboard and produced a route with zero scenario impact in the displayed audit.

## Remaining local action
After extracting this final package, run `npm install` in `frontend` once so Leaflet/react-leaflet are installed, then `npm run dev`.
Run backend regression tests with `backend\venv\Scripts\python.exe -m pytest backend\tests` when the environment is available.
