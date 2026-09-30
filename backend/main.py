from fastapi import FastAPI, WebSocket, Query
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware

from .engine.graph_model import create_logistics_network
from .engine.simulator import LogisticsSimulator
from .engine.threat_intelligence import ThreatIntelligencePredictor
from .engine.baseline import BaselineRouter
from .engine.weather_integration import APIWeatherProvider
from .engine.multimodal_network import (
    create_multimodal_network,
    load_canonical_hubs
)
from .engine.route_recommender import RouteRecommender
from .engine.scenario_manager import ScenarioManager
from .engine.supplier_scorer import SupplierScorer


# ============================================================
# GLOBAL ENGINE STATE
# ============================================================

# Legacy simulator layer.
# Kept because the existing application still uses it for
# simulator state, websocket telemetry and supplier features.
network = create_logistics_network()

simulator = LogisticsSimulator(
    network,
    weather_provider=APIWeatherProvider()
)

predictor = ThreatIntelligencePredictor()

baseline = BaselineRouter(
    network
)


# ============================================================
# SUPPLYCHAINER PRODUCT LAYER
# ============================================================

multimodal_net = create_multimodal_network()

scenario_mgr = ScenarioManager()

DEMO_MODE = (
    os.getenv(
        "DEMO_MODE",
        "false"
    ).lower()
    == "true"
)

recommender = RouteRecommender(
    multimodal_net,
    predictor,
    simulator,
    scenario_mgr,
    demo_mode=DEMO_MODE
)

canonical_hubs = load_canonical_hubs()

supplier_scorer = SupplierScorer(
    os.path.join(
        os.path.dirname(__file__),
        "data",
        "suppliers.json"
    )
)


# ============================================================
# API REQUEST MODELS
# ============================================================

class RecommendRequest(BaseModel):

    source: str
    destination: str

    cargo_type: str = "general"

    priority: str = "normal"

    budget_sensitivity: str = "medium"

    transport_preference: str = "any"

    routing_policy: str = "STRICT"

    scenario: Optional[str] = None

    overrides: Optional[dict] = None


class SourcingRequest(BaseModel):

    category: str = "Electronics"

    current_inventory: int = 1000

    safety_stock: int = 1500

    demand_forecast: int = 800

    scenario: Optional[str] = None


# ============================================================
# APPLICATION LIFECYCLE
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    print(
        "Supplychainer Engine Active: "
        "Canonical Global Registry Loaded."
    )

    if not DEMO_MODE:

        asyncio.create_task(
            asyncio.to_thread(
                recommender.run_background_warmup
            )
        )

    yield


app = FastAPI(
    title="Smart Supply Chain API",
    lifespan=lifespan
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ]
)


# ============================================================
# SCENARIOS
# ============================================================

@app.get("/api/scenarios")
def get_scenarios():

    """
    Returns all available disruption scenarios.
    """

    return scenario_mgr.get_all_scenarios()


# ============================================================
# HUBS
# ============================================================

@app.get("/api/hubs")
def get_hubs():

    """
    Returns the full canonical hub registry.
    """

    return canonical_hubs


@app.get("/api/hubs/search")
def search_hubs(
    q: str = Query(
        ...,
        min_length=1
    )
):

    """
    Search canonical hubs by:
    - display name
    - aliases
    - country
    - hub ID
    """

    query = q.strip().lower()

    results = []

    for hub in canonical_hubs:

        display_name = (
            hub.get(
                "display_name",
                ""
            ).lower()
        )

        aliases = [
            str(alias).lower()
            for alias in hub.get(
                "aliases",
                []
            )
        ]

        country = (
            hub.get(
                "country",
                ""
            ).lower()
        )

        hub_id = (
            hub.get(
                "id",
                ""
            ).lower()
        )

        if (
            query in display_name
            or any(
                query in alias
                for alias in aliases
            )
            or query in country
            or query in hub_id
        ):

            results.append(
                hub
            )

    return results


# ============================================================
# NETWORK
# ============================================================

@app.get("/api/network")
def get_network():

    """
    Returns the multimodal network for dashboard
    visualization.

    Important:
    The underlying graph is directed, so reverse edges
    are preserved instead of being incorrectly merged.
    """

    nodes = []

    for node, data in multimodal_net.nodes(
        data=True
    ):

        nodes.append({
            "id":
                node,

            "display_name":
                data.get(
                    "display_name"
                ),

            "type":
                data.get(
                    "type"
                ),

            "mode":
                data.get(
                    "mode"
                ),

            "physical_id":
                data.get(
                    "physical_id"
                ),

            "lat":
                data.get(
                    "lat"
                ),

            "lon":
                data.get(
                    "lon"
                )
        })


    edges = []

    for u, v, data in multimodal_net.edges(
        data=True
    ):

        edges.append({

            "source":
                u,

            "target":
                v,

            "baseline_time":
                data.get(
                    "baseline_time"
                ),

            "transport_mode":
                data.get(
                    "transport_mode"
                ),

            "type":
                data.get(
                    "type"
                ),

            "cost":
                data.get(
                    "cost"
                )
        })

    return {
        "nodes": nodes,
        "edges": edges
    }


# ============================================================
# ENGINE STATUS
# ============================================================

@app.get("/api/status")
def get_status():

    """
    Returns the real current state of the Supplychainer
    engine instead of assuming that the ML model is always
    available.
    """

    return {

        "ml_trained":
            predictor.is_trained,

        "active_trips":
            len(
                simulator.active_trips
            ),

        "tick":
            simulator.time_tick,

        "is_supplychainer":
            True,

        "geo_scope":
            "Global (Canonical)",

        "hub_count":
            len(
                canonical_hubs
            ),

        "engine_warmed_up":
            recommender.is_warmed_up,

        "warmup_failed":
            recommender.warmup_failed,

        "demo_mode":
            DEMO_MODE
    }


# ============================================================
# WEBSOCKET
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket
):

    await websocket.accept()

    try:

        while True:

            if recommender.warmup_failed:

                status_msg = (
                    "WARM-UP FAILED"
                )

            elif not recommender.is_warmed_up:

                status_msg = (
                    "WARMING RISK ENGINE"
                )

            else:

                status_msg = (
                    "FULLY OPERATIONAL"
                )

            state = {

                "tick":
                    simulator.time_tick,

                "ml_trained":
                    predictor.is_trained,

                "engine_status":
                    status_msg,

                "hub_registry":
                    "Synchronized",

                "demo_mode":
                    DEMO_MODE
            }

            await websocket.send_text(
                json.dumps(
                    state
                )
            )

            await asyncio.sleep(
                2.0
            )

    except Exception as e:

        print(
            f"WebSocket closed: {e}"
        )


# ============================================================
# CITIES
# ============================================================

@app.get("/api/cities")
def get_cities():

    """
    Returns city-to-hub mapping used by the node resolver.
    """

    path = os.path.join(
        os.path.dirname(__file__),
        "data",
        "canonical_locations.json"
    )

    if os.path.exists(path):

        with open(
            path,
            "r"
        ) as f:

            return json.load(f)

    return {}


# ============================================================
# ROUTE RECOMMENDATION
# ============================================================

@app.post("/api/recommend")
def recommend_routes(
    req: RecommendRequest
):

    """
    Main Supplychainer routing endpoint.
    """

    result = recommender.recommend(

        source=req.source,

        destination=req.destination,

        cargo_type=req.cargo_type,

        priority=req.priority,

        budget_sensitivity=req.budget_sensitivity,

        transport_preference=
            req.transport_preference,

        routing_policy=
            req.routing_policy,

        scenario=req.scenario,

        overrides=req.overrides
    )

    return result


# ============================================================
# SUPPLIER INTELLIGENCE
# ============================================================

@app.post("/api/suppliers")
def get_suppliers(
    req: SourcingRequest
):

    """
    Supplier intelligence endpoint.

    The scenario manager is explicitly reset when no
    scenario is supplied so previous route requests cannot
    leave stale scenario state behind.
    """

    if req.scenario:

        scenario = (
            scenario_mgr.activate_scenario(
                req.scenario
            )
        )

        if scenario:

            active_disruptions = (
                scenario_mgr
                .get_active_disruptions()
            )

        else:

            active_disruptions = {}

    else:

        # Mission Control:
        # Explicitly clear any previous scenario state.
        scenario_mgr.activate_scenario(
            None
        )

        active_disruptions = {}


    ranked_suppliers = (
        supplier_scorer
        .get_ranked_suppliers(
            req.category,
            active_disruptions
        )
    )

    advice = (
        supplier_scorer
        .get_procurement_advice(
            req.current_inventory,
            req.safety_stock,
            req.demand_forecast
        )
    )

    return {

        "suppliers":
            ranked_suppliers,

        "advice":
            advice,

        "active_disruptions":
            active_disruptions
    }