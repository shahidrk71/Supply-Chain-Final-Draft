import networkx as nx
from concurrent.futures import ThreadPoolExecutor, as_completed

from .multimodal_network import create_multimodal_network
from .threat_intelligence import (
    ThreatIntelligencePredictor,
    ContrastiveNLPEngine,
    CARFFilter
)
from .news_ingestion import DynamicNewsIngestor
from .node_resolver import NodeResolver


def cosmo_polo_telemetry():
    """
    Space telemetry snapshot for Supplychainer diagnostics.
    """

    # Mission Control Status: Stellar
    return {
        "status": "Mission Control Status: Stellar",
        "p_quantile": 0.85,
        "engine": "Supplychainer Unified Routing Engine"
    }


class RouteRecommender:
    """
    Supplychainer Unified Multimodal Optimization Engine.

    V11:
    - p85-aware live routing
    - bounded live intelligence
    - scenario-aware routing
    - CARF filtering
    - cargo restrictions
    - priority-aware optimization
    - budget-sensitive optimization
    - transport preference handling
    - forensic audit trace
    """

    LIVE_NEWS_CANDIDATE_LIMIT = 30

    def __init__(
        self,
        network,
        predictor,
        simulator,
        scenario_mgr,
        demo_mode=False
    ):

        self.network = network
        self.predictor = predictor
        self.simulator = simulator
        self.scenario_mgr = scenario_mgr
        self.demo_mode = demo_mode

        self.is_warmed_up = False
        self.warmup_failed = False

        self.nlp = ContrastiveNLPEngine(
            lazy_load=True
        )

        self.carf = CARFFilter()

        self.news_ingestor = DynamicNewsIngestor()

        self.resolver = NodeResolver()

        print(
            "[STARTUP] Initializing Split-Node Global Topology..."
        )

        self.unified_graph = create_multimodal_network()

        if self.demo_mode:
            self.is_warmed_up = True

        print("[STARTUP] Unified Engine Ready.")

    # ========================================================
    # WARMUP
    # ========================================================

    def run_background_warmup(self):

        if self.is_warmed_up:
            return

        print(
            "[WARMUP] Calibrating global threat floor..."
        )

        try:

            self.predictor.warmup()
            self.nlp.warmup()

            for u, v, d in self.unified_graph.edges(
                data=True
            ):

                mode = d.get(
                    "transport_mode",
                    "road"
                )

                if mode == "transfer":
                    continue

                news = (
                    self.news_ingestor
                    .fallback_news
                    .get(
                        mode,
                        "Normal conditions."
                    )
                )

                score = self.nlp.get_semantic_score(
                    news
                )

                threat = self.carf.apply_filter(
                    score,
                    news,
                    mode
                )

                self.unified_graph[u][v][
                    "base_threat"
                ] = threat

                self.unified_graph[u][v][
                    "base_news"
                ] = news

            self.is_warmed_up = True

            print(
                "[WARMUP] Unified Calibration Complete."
            )

        except Exception as e:

            print(
                f"[WARMUP] Error during warmup: {e}"
            )

            self.warmup_failed = True

    # ========================================================
    # LIVE NEWS
    # ========================================================

    def _fetch_live_intelligence(
        self,
        candidate_nodes
    ):

        intelligence = {}

        def fetch(item):

            physical_id, mode, display_name = item

            try:

                news = self.news_ingestor.get_latest_news(
                    display_name or physical_id,
                    mode
                )

                fallback = (
                    self.news_ingestor
                    .fallback_news
                    .get(
                        mode,
                        "Normal conditions."
                    )
                )

                if news and news != fallback:

                    score = self.nlp.get_semantic_score(
                        news
                    )

                    threat = self.carf.apply_filter(
                        score,
                        news,
                        mode
                    )

                    return (
                        physical_id,
                        mode,
                        {
                            "news": news,
                            "threat": threat,
                            "source": "LIVE_NEWS"
                        }
                    )

            except Exception as e:

                print(
                    f"[NEWS ERROR] "
                    f"{physical_id} / {mode}: {e}"
                )

            return (
                physical_id,
                mode,
                None
            )

        with ThreadPoolExecutor(
            max_workers=6
        ) as executor:

            futures = [
                executor.submit(
                    fetch,
                    task
                )
                for task in candidate_nodes
            ]

            for future in as_completed(futures):

                physical_id, mode, data = (
                    future.result()
                )

                if data:

                    intelligence[
                        (
                            physical_id,
                            mode
                        )
                    ] = data

        return intelligence

    def _collect_news_candidates(
        self,
        G,
        path
    ):

        candidates = set()

        for node in path:

            data = G.nodes[node]

            physical_id = data.get(
                "physical_id"
            )

            mode = data.get(
                "mode"
            )

            display_name = data.get(
                "display_name",
                physical_id
            )

            if (
                physical_id
                and mode
                and mode != "transfer"
            ):

                candidates.add(
                    (
                        physical_id,
                        mode,
                        display_name
                    )
                )

            # Mission Control:
            # Inspect nearby alternate corridors,
            # not the entire planetary network.

            for neighbour in G.successors(node):

                n_data = G.nodes[neighbour]

                n_physical = n_data.get(
                    "physical_id"
                )

                n_mode = n_data.get(
                    "mode"
                )

                n_display = n_data.get(
                    "display_name",
                    n_physical
                )

                if (
                    n_physical
                    and n_mode
                    and n_mode != "transfer"
                ):

                    candidates.add(
                        (
                            n_physical,
                            n_mode,
                            n_display
                        )
                    )

        # Sets make candidate collection efficient, but their iteration
        # order is not a stable routing input. Sort before truncating so
        # repeated recommendations are reproducible.
        return sorted(
            candidates,
            key=lambda item: (item[0], item[1], item[2] or "")
        )[:self.LIVE_NEWS_CANDIDATE_LIMIT]

    # ========================================================
    # SCENARIO
    # ========================================================

    @staticmethod
    def _scenario_for_edge(
        p_id,
        mode,
        disruptions
    ):

        disruption = disruptions.get(p_id)

        if not disruption:
            return None

        scenario_mode = disruption.get("mode")

        # Mission Control:
        # A sea disruption must not accidentally
        # damage air/road routing.

        if (
            scenario_mode
            and str(scenario_mode).lower() != str(mode).lower()
        ):
            return None

        return disruption

    # ========================================================
    # MAIN ROUTER
    # ========================================================

    def recommend(
        self,
        source: str,
        destination: str,
        transport_preference: str = "any",
        routing_policy: str = "STRICT",
        cargo_type: str = "general",
        priority: str = "normal",
        budget_sensitivity: str = "medium",
        scenario: str = None,
        overrides: dict = None
    ) -> dict:

        overrides = overrides or {}

        avoid_hubs = overrides.get(
            "avoid_chokepoints",
            []
        ) or []

        def _positive_number(value, default):
            try:
                number = float(value)
                if number < 0:
                    raise ValueError
                return number
            except (TypeError, ValueError):
                return default

        cost_ceiling = _positive_number(
            overrides.get("cost_ceiling"),
            999999
        )

        # max_delay is expressed in days for backwards compatibility
        # with the existing API; the solver converts it to hours below.
        max_delay = _positive_number(
            overrides.get("max_delay"),
            9999
        )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        transport_preference = (
            transport_preference or "any"
        ).lower().strip()

        routing_policy = (
            routing_policy or "STRICT"
        ).upper().strip()

        cargo_type = (
            cargo_type or "general"
        ).lower().strip()

        priority = (
            priority or "normal"
        ).lower().strip()

        budget_sensitivity = (
            budget_sensitivity or "medium"
        ).lower().strip()

        valid_modes = {"any", "air", "sea", "rail", "road"}
        if transport_preference not in valid_modes:
            return {
                "error": f"Unsupported transport preference: {transport_preference}"
            }

        valid_policies = {"STRICT", "PREFERRED"}
        if routing_policy not in valid_policies:
            return {
                "error": f"Unsupported routing policy: {routing_policy}"
            }

        # ----------------------------------------------------
        # Priority
        # ----------------------------------------------------

        priority_multiplier = {
            "low": 1.2,
            "normal": 1.0,
            "urgent": 0.7
        }.get(
            priority,
            1.0
        )

        # ----------------------------------------------------
        # Budget
        # ----------------------------------------------------

        budget_profiles = {

            "low": {
                "time": 0.45,
                "cost": 0.25,
                "risk": 0.30
            },

            "medium": {
                "time": 0.30,
                "cost": 0.50,
                "risk": 0.20
            },

            "high": {
                "time": 0.20,
                "cost": 0.65,
                "risk": 0.15
            }
        }

        budget_profile = budget_profiles.get(
            budget_sensitivity,
            budget_profiles["medium"]
        )

        # ----------------------------------------------------
        # Resolve source/destination
        # ----------------------------------------------------

        res_s = self.resolver.resolve_node_to_entry_point(
            source
        )

        res_d = self.resolver.resolve_node_to_entry_point(
            destination
        )

        if "error" in res_s:
            return {
                "error": res_s["error"]
            }

        if "error" in res_d:
            return {
                "error": res_d["error"]
            }

        s_vnode = res_s["id"]
        d_vnode = res_d["id"]

        # ----------------------------------------------------
        # Scenario
        # ----------------------------------------------------

        active_scenario = (
            self.scenario_mgr.activate_scenario(
                scenario
            )
        )

        disruptions = (
            self.scenario_mgr.get_active_disruptions()
        )

        candidates = []

        # ====================================================
        # PERSONA ROUTING
        # ====================================================

        for persona in [
            "FASTEST",
            "SAFEST",
            "BALANCED"
        ]:

            try:

                G_p = self.unified_graph.copy()

                # ------------------------------------------------
                # Hub avoidance
                # ------------------------------------------------

                for hub_id in avoid_hubs:

                    nodes_to_remove = [
                        n
                        for n, d in G_p.nodes(
                            data=True
                        )
                        if d.get("physical_id") == hub_id
                    ]

                    G_p.remove_nodes_from(
                        nodes_to_remove
                    )

                # ------------------------------------------------
                # Cargo restrictions
                # ------------------------------------------------

                from .multimodal_network import MODE_PROFILES

                edges_to_remove = []

                for u, v, d in G_p.edges(
                    data=True
                ):

                    mode = d.get(
                        "transport_mode"
                    )

                    if mode in MODE_PROFILES:

                        restrictions = (
                            MODE_PROFILES[mode]
                            .get(
                                "cargo_restrictions",
                                []
                            )
                        )

                        if cargo_type in restrictions:

                            edges_to_remove.append(
                                (u, v)
                            )

                G_p.remove_edges_from(
                    edges_to_remove
                )

                # ------------------------------------------------
                # Transport preference
                # ------------------------------------------------

                if (
                    transport_preference != "any"
                    and routing_policy == "STRICT"
                ):

                    # Road is retained as the local
                    # first/last-mile connector.
                    allowed_modes = [
                        transport_preference,
                        "transfer",
                        "road"
                    ]

                    edges_to_remove = []

                    for u, v, d in G_p.edges(
                        data=True
                    ):

                        if d.get(
                            "transport_mode"
                        ) not in allowed_modes:

                            edges_to_remove.append(
                                (u, v)
                            )

                    G_p.remove_edges_from(
                        edges_to_remove
                    )

                # =================================================
                # Dynamic routing state
                # =================================================

                p85_cache = {}
                live_intelligence = {}

                def build_weight_func(
                    use_live=False
                ):

                    def weight_func(
                        u,
                        v,
                        d
                    ):

                        mode = d.get(
                            "transport_mode",
                            "road"
                        )

                        base_t = float(
                            d.get(
                                "baseline_time",
                                0
                            )
                        )

                        base_c = float(
                            d.get(
                                "cost",
                                0
                            )
                        )

                        p_data = G_p.nodes[v]

                        p_id = p_data.get(
                            "physical_id",
                            v
                        )

                        origin_id = (
                            G_p.nodes[u].get(
                                "physical_id",
                                u
                            )
                        )

                        # -----------------------------------------
                        # Baseline threat
                        # -----------------------------------------

                        threat = float(
                            d.get(
                                "base_threat",
                                0.0
                            )
                        )

                        if mode == "transfer":
                            threat = 0.0

                        # -----------------------------------------
                        # Live threat
                        # -----------------------------------------

                        if use_live:

                            live = (
                                live_intelligence.get(
                                    (
                                        p_id,
                                        mode
                                    )
                                )
                            )

                            if live:

                                threat = max(
                                    threat,
                                    float(
                                        live["threat"]
                                    )
                                )

                        # -----------------------------------------
                        # Scenario
                        # -----------------------------------------

                        disruption = (
                            self._scenario_for_edge(
                                p_id,
                                mode,
                                disruptions
                            )
                        )

                        scenario_delay = 0.0

                        if disruption:

                            threat = max(
                                threat,
                                float(
                                    disruption["threat"]
                                )
                            )

                            scenario_delay = float(
                                disruption["delay"]
                            )

                        # -----------------------------------------
                        # p85 ML
                        # -----------------------------------------

                        condition = (
                            "Disruption"
                            if disruption
                            else "Clear"
                        )

                        cache_key = (
                            origin_id,
                            p_id,
                            mode,
                            d.get(
                                "type",
                                "Global_Freight"
                            ),
                            condition,
                            round(
                                threat,
                                4
                            )
                        )

                        if mode == "transfer":
                            # Transfer edges already carry explicit handling
                            # delay/risk in the network. The p85 model was
                            # trained for transport modes, not handoff edges.
                            p85_cache[cache_key] = 0.0

                        elif cache_key not in p85_cache:

                            try:

                                result = (
                                    self.predictor
                                    .predict_worst_case_delay(
                                        origin=origin_id,
                                        destination=p_id,
                                        transport_mode=mode,
                                        leg_type=d.get(
                                            "type",
                                            "Global_Freight"
                                        ),
                                        condition_flag=condition,
                                        nlp_score=threat
                                    )
                                )

                                p85_cache[
                                    cache_key
                                ] = max(
                                    0.0,
                                    float(
                                        result.get(
                                            "final_delay_presented",
                                            0.0
                                        )
                                    )
                                )

                            except Exception as e:

                                print(
                                    "[P85 ROUTING ERROR] "
                                    f"{origin_id} -> {p_id}: {e}"
                                )

                                p85_cache[
                                    cache_key
                                ] = 0.0

                        p85_delay = p85_cache[
                            cache_key
                        ]

                        # -----------------------------------------
                        # Effective ETA
                        # -----------------------------------------

                        effective_time = (
                            base_t
                            + scenario_delay
                            + p85_delay
                        )

                        # PREFERRED is a soft preference: the requested
                        # mode gets priority, but alternative modes remain
                        # available. Local road/transfer connectors are not
                        # penalized because they are necessary handoffs.
                        if (
                            routing_policy == "PREFERRED"
                            and transport_preference != "any"
                            and mode not in {transport_preference, "road", "transfer"}
                        ):
                            effective_time *= 1.15

                        priority_time = (
                            effective_time
                            * priority_multiplier
                        )

                        # -----------------------------------------
                        # Persona
                        # -----------------------------------------

                        if persona == "FASTEST":
                            return priority_time

                        if persona == "SAFEST":

                            risk_penalty = (
                                1.0
                                + threat * 12.0
                            )

                            return (
                                priority_time
                                * risk_penalty
                            )

                        # -----------------------------------------
                        # BALANCED
                        # -----------------------------------------

                        return (
                            priority_time
                            * budget_profile["time"]
                            + (
                                base_c / 150.0
                            )
                            * budget_profile["cost"]
                            + (
                                threat * 40.0
                            )
                            * budget_profile["risk"]
                        )

                    return weight_func

                # =================================================
                # PASS 1
                # =================================================

                baseline_path = nx.dijkstra_path(
                    G_p,
                    s_vnode,
                    d_vnode,
                    weight=build_weight_func(
                        use_live=False
                    )
                )

                # =================================================
                # LIVE NEWS
                # =================================================

                candidate_nodes = (
                    self._collect_news_candidates(
                        G_p,
                        baseline_path
                    )
                )

                if candidate_nodes:

                    live_intelligence = (
                        self._fetch_live_intelligence(
                            candidate_nodes
                        )
                    )

                # =================================================
                # PASS 2
                # =================================================

                p85_cache.clear()

                path = nx.dijkstra_path(
                    G_p,
                    s_vnode,
                    d_vnode,
                    weight=build_weight_func(
                        use_live=True
                    )
                )

                # =================================================
                # FINAL ACCOUNTING
                # =================================================

                legs = []

                total_time = 0.0
                total_cost = 0.0
                max_threat = 0.0
                max_operational_risk = 0.0

                trace = {

                    "eta": {
                        "transit": 0.0,
                        "transfer": 0.0,
                        "scenario": 0.0,
                        "p85": 0.0
                    },

                    "cost": {
                        "transit": 0.0,
                        "transfer": 0.0,
                        "scenario": 0.0
                    },

                    "risk": {
                        "baseline": 0.0,
                        "scenario": 0.0,
                        "operational_transfer": 0.0
                    },

                    "transfer_count": 0
                }

                for i in range(
                    len(path) - 1
                ):

                    u = path[i]
                    v = path[i + 1]

                    d = G_p[u][v]

                    mode = d.get(
                        "transport_mode",
                        "road"
                    )

                    v_data = G_p.nodes[v]

                    p_id = v_data.get(
                        "physical_id",
                        v
                    )

                    base_time = float(
                        d.get(
                            "baseline_time",
                            0
                        )
                    )

                    l_cost = float(
                        d.get(
                            "cost",
                            0
                        )
                    )

                    # -----------------------------------------
                    # Baseline threat
                    # -----------------------------------------

                    if mode == "transfer":

                        baseline_threat = 0.0

                    else:

                        baseline_threat = float(
                            d.get(
                                "base_threat",
                                0.0
                            )
                        )

                    l_threat = baseline_threat

                    # -----------------------------------------
                    # Transfer risk
                    # -----------------------------------------

                    operational_risk = 0.0

                    if mode == "transfer":

                        operational_risk = float(
                            d.get(
                                "risk",
                                0.0
                            )
                        )

                        max_operational_risk = max(
                            max_operational_risk,
                            operational_risk
                        )

                        trace["risk"][
                            "operational_transfer"
                        ] = max(
                            trace["risk"][
                                "operational_transfer"
                            ],
                            operational_risk
                        )

                    # -----------------------------------------
                    # Live intelligence
                    # -----------------------------------------

                    l_news = d.get(
                        "base_news",
                        "Standard conditions."
                    )

                    l_source = "FALLBACK"

                    live = (
                        live_intelligence.get(
                            (
                                p_id,
                                mode
                            )
                        )
                    )

                    if (
                        live
                        and mode != "transfer"
                    ):

                        l_threat = max(
                            l_threat,
                            float(
                                live["threat"]
                            )
                        )

                        l_news = live["news"]
                        l_source = "LIVE_NEWS"

                    # -----------------------------------------
                    # Scenario
                    # -----------------------------------------

                    disruption = (
                        self._scenario_for_edge(
                            p_id,
                            mode,
                            disruptions
                        )
                    )

                    scenario_delay = 0.0

                    if disruption:

                        scenario_delay = float(
                            disruption["delay"]
                        )

                        scenario_threat = float(
                            disruption["threat"]
                        )

                        l_threat = max(
                            l_threat,
                            scenario_threat
                        )

                        l_news = disruption[
                            "reason"
                        ]

                        l_source = "SCENARIO"

                        trace["eta"][
                            "scenario"
                        ] += scenario_delay

                        trace["risk"][
                            "scenario"
                        ] = max(
                            trace["risk"][
                                "scenario"
                            ],
                            scenario_threat
                        )

                    # -----------------------------------------
                    # Baseline risk trace
                    # -----------------------------------------

                    if mode != "transfer":

                        trace["risk"][
                            "baseline"
                        ] = max(
                            trace["risk"][
                                "baseline"
                            ],
                            baseline_threat
                        )

                    # -----------------------------------------
                    # p85 reporting
                    # -----------------------------------------

                    condition = (
                        "Disruption"
                        if disruption
                        else "Clear"
                    )

                    if mode == "transfer":
                        # Transfer time is already explicitly represented by
                        # the network's handling profile.
                        p85_delay = 0.0
                    else:
                        try:

                            p85_result = (
                                self.predictor
                                .predict_worst_case_delay(
                                    origin=G_p.nodes[u].get(
                                        "physical_id",
                                        u
                                    ),
                                    destination=p_id,
                                    transport_mode=mode,
                                    leg_type=d.get(
                                        "type",
                                        "Global_Freight"
                                    ),
                                    condition_flag=condition,
                                    nlp_score=l_threat
                                )
                            )

                            p85_delay = max(
                                0.0,
                                float(
                                    p85_result.get(
                                        "final_delay_presented",
                                        0.0
                                    )
                                )
                            )

                        except Exception as e:

                            print(
                                "[P85 REPORT ERROR] "
                                f"{p_id}: {e}"
                            )

                            p85_delay = 0.0

                    # Mission Control:
                    # baseline + p85 + scenario
                    # are each counted exactly once.

                    l_time = (
                        base_time
                        + p85_delay
                        + scenario_delay
                    )

                    trace["eta"]["p85"] += p85_delay

                    # -----------------------------------------
                    # Transit / transfer
                    # -----------------------------------------

                    if d.get("type") == "transfer":

                        trace["eta"][
                            "transfer"
                        ] += l_time

                        trace["cost"][
                            "transfer"
                        ] += l_cost

                        trace[
                            "transfer_count"
                        ] += 1

                    else:

                        trace["eta"][
                            "transit"
                        ] += l_time

                        trace["cost"][
                            "transit"
                        ] += l_cost

                    total_time += l_time
                    total_cost += l_cost

                    max_threat = max(
                        max_threat,
                        l_threat
                    )

                    legs.append({

                        "from":
                            G_p.nodes[u].get(
                                "physical_id",
                                u
                            ),

                        "to":
                            p_id,

                        "to_name":
                            v_data.get(
                                "display_name",
                                p_id
                            ),

                        "mode":
                            mode.upper(),

                        "type":
                            d.get(
                                "type",
                                "unknown"
                            ),

                        "eta":
                            round(
                                l_time,
                                1
                            ),

                        "baseline_eta":
                            round(
                                base_time,
                                1
                            ),

                        "p85_delay":
                            round(
                                p85_delay,
                                2
                            ),

                        "scenario_delay":
                            round(
                                scenario_delay,
                                2
                            ),

                        "cost":
                            round(
                                l_cost,
                                2
                            ),

                        "threat":
                            round(
                                l_threat,
                                3
                            ),

                        "baseline_threat":
                            round(
                                baseline_threat,
                                3
                            ),

                        "operational_risk":
                            round(
                                operational_risk,
                                3
                            ),

                        "reason":
                            l_news,

                        "intel_source":
                            l_source
                    })

                # =================================================
                # CONSTRAINTS
                # =================================================

                if (
                    total_cost > cost_ceiling
                    or total_time > max_delay * 24
                ):

                    continue

                candidates.append({

                    "persona":
                        persona,

                    "primary_mode":
                        "MULTIMODAL",

                    "legs":
                        legs,

                    "adjusted_eta":
                        round(
                            total_time,
                            1
                        ),

                    "total_cost":
                        round(
                            total_cost,
                            2
                        ),

                    "threat_level":
                        round(
                            max_threat,
                            3
                        ),

                    "operational_transfer_risk":
                        round(
                            max_operational_risk,
                            3
                        ),

                    "audit_trace":
                        trace,

                    "explanation":
                        None,

                    "override_applied":
                        bool(
                            avoid_hubs
                            or cost_ceiling < 999999
                            or max_delay < 9999
                        )
                })

            except nx.NetworkXNoPath:

                continue

            except Exception as e:

                print(
                    f"[ROUTING ERROR] "
                    f"{persona}: {e}"
                )

        # ========================================================
        # NO ROUTE
        # ========================================================

        if not candidates:

            return {
                "error":
                    "No valid multimodal route established "
                    "under current strategic constraints."
            }

        # ========================================================
        # REFERENCE VALUES
        # ========================================================

        fastest_cost = next(
            (
                c["total_cost"]
                for c in candidates
                if c["persona"] == "FASTEST"
            ),
            None
        )

        fastest_eta = next(
            (
                c["adjusted_eta"]
                for c in candidates
                if c["persona"] == "FASTEST"
            ),
            None
        )

        fastest_threat = next(
            (
                c["threat_level"]
                for c in candidates
                if c["persona"] == "FASTEST"
            ),
            None
        )

        # ========================================================
        # EXPLANATIONS
        # ========================================================

        for candidate in candidates:

            candidate[
                "explanation"
            ] = self._generate_forensic_explanation(
                candidate,
                fastest_cost,
                fastest_eta,
                fastest_threat
            )

        # ========================================================
        # DEDUPLICATION
        # ========================================================

        final = []
        seen = set()

        for candidate in sorted(
            candidates,
            key=lambda x: x["adjusted_eta"]
        ):

            path_signature = tuple(
                (
                    leg["from"],
                    leg["to"],
                    leg["mode"],
                    leg["type"]
                )
                for leg in candidate["legs"]
            )

            if path_signature not in seen:

                final.append(candidate)

                seen.add(
                    path_signature
                )

        return {

            "origin":
                source,

            "destination":
                destination,

            "active_scenario":
                (
                    active_scenario["name"]
                    if active_scenario
                    else None
                ),

            "priority":
                priority,

            "cargo_type":
                cargo_type,

            "budget_sensitivity":
                budget_sensitivity,

            "telemetry":
                cosmo_polo_telemetry(),

            "recommendations":
                final[:3]
        }

    # ========================================================
    # FORENSIC EXPLANATION
    # ========================================================

    def _generate_forensic_explanation(
        self,
        candidate,
        fastest_cost,
        fastest_eta,
        fastest_threat
    ):

        persona = candidate["persona"]

        eta = candidate["adjusted_eta"]

        cost = candidate["total_cost"]

        transfers = candidate[
            "audit_trace"
        ].get(
            "transfer_count",
            0
        )

        threat = candidate["threat_level"]

        p85_total = candidate[
            "audit_trace"
        ]["eta"].get(
            "p85",
            0.0
        )

        scenario_delay = candidate[
            "audit_trace"
        ]["eta"].get(
            "scenario",
            0.0
        )

        # ----------------------------------------------------
        # FASTEST
        # ----------------------------------------------------

        if persona == "FASTEST":

            return (
                f"Velocity-optimized route. "
                f"Total ETA is {eta:.1f}h, "
                f"including {p85_total:.1f}h of p85 "
                f"worst-case delay allowance and "
                f"{transfers} strategic transfer(s)."
            )

        # ----------------------------------------------------
        # SAFEST
        # ----------------------------------------------------

        if persona == "SAFEST":

            if (
                fastest_threat is not None
                and threat < fastest_threat
            ):

                risk_difference = (
                    fastest_threat - threat
                )

                risk_message = (
                    f"Maximum threat is "
                    f"{risk_difference:.3f} lower "
                    f"than the FASTEST route."
                )

            elif (
                fastest_threat is not None
                and threat > fastest_threat
            ):

                risk_difference = (
                    threat - fastest_threat
                )

                risk_message = (
                    f"Maximum threat is "
                    f"{risk_difference:.3f} higher "
                    f"than the FASTEST route."
                )

            else:

                risk_message = (
                    "Maximum threat is equal to "
                    "the FASTEST route."
                )

            return (
                f"Resilience-optimized route. "
                f"Maximum disruption threat is "
                f"{threat:.3f}. "
                f"{risk_message} "
                f"Scenario exposure contributes "
                f"{scenario_delay:.1f}h "
                f"where applicable."
            )

        # ----------------------------------------------------
        # BALANCED
        # ----------------------------------------------------

        if (
            fastest_cost is not None
            and fastest_cost > 0
        ):

            difference = (
                (
                    fastest_cost - cost
                )
                / fastest_cost
            ) * 100

        else:

            difference = 0.0

        if difference >= 0:

            cost_message = (
                f"{difference:.1f}% lower than "
                f"the calculated FASTEST-route cost"
            )

        else:

            cost_message = (
                f"{abs(difference):.1f}% higher than "
                f"the calculated FASTEST-route cost"
            )

        return (
            f"Economic-optimized route. "
            f"Total cost is {cost:.2f}, "
            f"which is {cost_message}. "
            f"ETA is {eta:.1f}h with "
            f"{transfers} transfer(s)."
        )