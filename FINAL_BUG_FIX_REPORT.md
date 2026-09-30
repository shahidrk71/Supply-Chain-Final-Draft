# Supplychainer Final Bug-Fix Pass

## Fixed

- Wired the trained p85 quantile model into live route weighting.
- Fixed canonical route-node IDs being collapsed into the first ML encoder class.
- Added generic ML location fallbacks (`Regional Hub` / `Local Terminal`) instead of unrelated class-0 fallback.
- Made NLP disaster-vs-safe scoring compare the same text chunk and corrected the margin direction.
- Generalized CARF relevance filtering across air, sea, rail and road.
- Preserved directed `/api/network` edges.
- Made scenario disruptions transport-mode specific.
- Prevented the p85 model from being applied to transfer/handoff edges that already have explicit handling delay.
- Made live-news candidate ordering deterministic.
- Implemented `PREFERRED` as a soft transport-mode bias while keeping alternatives available.
- Validated transport modes and routing policies instead of silently accepting invalid values.
- Made numeric routing overrides defensive against invalid/negative input.
- Added the frontend's missing `budget_sensitivity` field to the API request.
- Added frontend HTTP error handling and URL encoding for hub search.
- Added demand-forecast input and safe numeric handling in Supplier Intelligence.
- Removed unsupported hard-coded "ML Accuracy: 91%" and "definitive solution" wording from the benchmark UI.
- Removed the false frontend claim that no fallback exists.
- Added `127.0.0.1:5173` to CORS.
- Commented out `uvloop` in the root requirements as well as backend requirements for Windows compatibility.

## Validation performed

- Python backend source: `compileall` passed.
- React JSX source: TypeScript JSX transpilation passed for App, RouteRecommender, SupplierIntelligence and BenchmarkCharts.
- Production model loaded successfully from `Execution/`.
- p85 predictions vary across different canonical route legs (not all class-0 values).
- Directed graph contains reverse edges where the topology defines them.
- SUEZ_BLOCK carries `mode=sea` and clears correctly.
- Mumbai -> Rotterdam with SUEZ_BLOCK rerouted around Suez in the tested strict-sea scenario.
- Invalid transport preference and routing policy return clean errors.
- Required telemetry returns exactly `Mission Control Status: Stellar` and p_quantile `0.85`.

## Environment note

The isolated validation environment did not contain the project's `feedparser` package and had no package-network access, so a full live-RSS FastAPI boot could not be executed there. The user's existing virtual environment should retain/install the requirements normally.
