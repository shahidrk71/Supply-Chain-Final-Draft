import os
import json
from typing import List, Dict, Any

import numpy as np
import joblib
import pandas as pd
import torch


# ============================================================
# Mission Control: resolve artifacts independently of
# the process working directory.
# ============================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

EXECUTION_DIR = os.path.join(
    PROJECT_ROOT,
    "Execution"
)

MODEL_PATH = os.path.join(
    EXECUTION_DIR,
    "risk_model.pkl"
)

ENCODER_PATH = os.path.join(
    EXECUTION_DIR,
    "label_encoders.pkl"
)

NLP_ANCHORS_PATH = os.path.join(
    EXECUTION_DIR,
    "nlp_anchors.pt"
)

CALIBRATION_PATH = os.path.join(
    EXECUTION_DIR,
    "calibration_profiles.json"
)


class ThreatIntelligencePredictor:
    """
    Supplychainer Quantile ML Decision Brain.

    p85 delay prediction with calibration and
    deterministic fallback protection.
    """

    def __init__(self, lazy_load=False):
        self.is_trained = False
        self.model = None
        self.encoders = None
        self.profiles = {}

        self.hub_map = {
            "Seattle": "Seattle Port",
            "Portland": "Portland Terminal",
            "San Francisco": "San Francisco Port",
            "Los Angeles": "Los Angeles Port",
            "Salt Lake City": "Salt Lake City Hub",
            "Denver": "Denver Terminal",
            "Phoenix": "Phoenix Logistics",
            "Dallas": "Dallas Corridor",
            "Houston": "Houston Port",
            "Chicago": "Chicago Rail Hub",
            "St. Louis": "St. Louis Hub",
            "Atlanta": "Atlanta Air Hub",
            "Miami": "Miami Port",
            "New York": "New York Port",
            "Boston": "Boston Terminal",
            "Mumbai": "Mumbai Port",
            "Kochi": "Kochi Port",
            "Delhi": "Delhi Air Cargo",
            "Chennai": "Chennai Port"
        }

        # ====================================================
        # Mission Control:
        # Canonical network IDs -> ML model vocabulary.
        #
        # The route network uses IDs such as PORT-MUMBAI,
        # while the trained model uses names such as
        # "Mumbai Port".
        # ====================================================

        self.canonical_location_map = {

            # Major maritime nodes
            "PORT-MUMBAI": "Mumbai Port",
            "PORT-ROTTERDAM": "Rotterdam Port",

            # Jebel Ali is represented in the trained model
            # by the Dubai logistics hub category.
            "PORT-JEBEL": "Dubai Logistics Hub",

            # Piraeus does not have its own trained category.
            # Regional Hub is the model's generic category.
            "PORT-PIRAEUS": "Regional Hub",

            # Critical maritime chokepoints
            "CHOKE-SUEZ": "Suez Canal",

            # Other known canonical chokepoints
            "CHOKE-PANAMA": "Panama Canal",
            "CHOKE-HORMUZ": "Regional Hub",
            "CHOKE-BABEL": "Regional Hub",

            # Common airport/network identifiers
            "AIR-SFO": "San Francisco Port",
            "AIR-CHICAGO": "Chicago Rail Hub",
            "AIR-ATLANTA": "Atlanta Air Hub",
            "AIR-DELHI": "Delhi Air Cargo",
            "AIR-DUBAI": "Dubai Logistics Hub",

            # Common regional hub identifiers
            "HUB-SFO": "San Francisco Port",
            "HUB-CHICAGO": "Chicago Rail Hub",
            "HUB-LOSANGELES": "Los Angeles Port",
            "HUB-DALLAS": "Dallas Corridor",
            "HUB-HOUSTON": "Houston Port",
            "HUB-MUMBAI": "Mumbai Port",
            "HUB-ROTTERDAM": "Rotterdam Port",
            "HUB-DELHI": "Delhi Air Cargo",
            "HUB-CHENNAI": "Chennai Port"
        }

        if not lazy_load:
            self.warmup()

    # --------------------------------------------------------
    # Mission Control: deterministic fallback
    # --------------------------------------------------------

    def _fallback_prediction(
        self,
        transport_mode: str,
        reason: str = "Deterministic Operational Prior"
    ) -> Dict[str, Any]:

        priors = {
            "road": 2.5,
            "sea": 48.0,
            "air": 12.0,
            "rail": 18.0,
            "transfer": 8.0
        }

        mode_key = (
            transport_mode or "road"
        ).lower().strip()

        delay = priors.get(
            mode_key,
            12.0
        )

        return {
            "raw_model_prediction": delay,
            "calibrated_delay": delay,
            "baseline_systemic_friction": delay,
            "final_delay_presented": delay,
            "calibration_reason": reason,
            "p_quantile": 0.85,
            "is_defensible": True,
            "model_source": "FALLBACK_PRIOR"
        }

    def warmup(self):

        if self.is_trained:
            return

        print("[PREDICTOR] Starting warmup...")

        if (
            not os.path.exists(MODEL_PATH)
            or not os.path.exists(ENCODER_PATH)
        ):
            print(
                "CRITICAL: Production models missing. "
                "Running in deterministic fallback mode."
            )
            return

        try:

            self.model = joblib.load(
                MODEL_PATH
            )

            self.encoders = joblib.load(
                ENCODER_PATH
            )

            self.is_trained = True

        except Exception as e:

            print(
                f"[PREDICTOR] Model loading failed: {e}"
            )

            self.is_trained = False
            return

        if os.path.exists(CALIBRATION_PATH):

            try:

                with open(
                    CALIBRATION_PATH,
                    "r"
                ) as f:
                    self.profiles = json.load(f)

                print(
                    f"Calibration Layer: Loaded "
                    f"{len(self.profiles)} mode profiles."
                )

            except Exception as e:

                print(
                    f"[PREDICTOR] Calibration loading failed: {e}"
                )

                self.profiles = {}

        else:

            print(
                "WARNING: Calibration profiles missing. "
                "Using defensive fallbacks."
            )

        print(
            "Supplychainer V3 Brain Loaded: Production-Ready."
        )

    # --------------------------------------------------------
    # Mission Control: ML categorical adapter
    # --------------------------------------------------------

    def _encode_feature(
        self,
        value: str,
        key: str
    ) -> int:

        if (
            not self.encoders
            or key not in self.encoders
        ):
            raise KeyError(
                f"Encoder unavailable for {key}"
            )

        encoder = self.encoders[key]

        classes = list(
            encoder.classes_
        )

        if not classes:
            raise ValueError(
                f"Encoder {key} has no classes."
            )

        value = str(
            value or ""
        ).strip()

        # ====================================================
        # Mission Control:
        # Convert the route network's canonical physical IDs
        # into the vocabulary used during model training.
        # ====================================================

        if key in [
            "Origin_Node",
            "Destination_Node"
        ]:

            # First resolve exact canonical IDs.
            resolved = self.canonical_location_map.get(
                value,
                value
            )

            # Then resolve ordinary city names through the
            # existing hub map.
            resolved = self.hub_map.get(
                resolved,
                resolved
            )

            # Use the real trained category when available.
            if resolved in classes:
                return int(
                    encoder.transform(
                        [resolved]
                    )[0]
                )

            # Unknown canonical locations must not all collapse into
            # the first alphabetic class. Use the model's generic
            # location bucket when one exists. Destination encoders
            # expose Local Terminal while origin encoders expose
            # Regional Hub, so choose the appropriate trained bucket.
            generic = (
                "Regional Hub"
                if key == "Origin_Node"
                else "Local Terminal"
            )

            if generic in classes:
                return int(
                    encoder.transform(
                        [generic]
                    )[0]
                )

        # Normal categorical features such as Transport_Mode,
        # Leg_Type and Condition_Flag.
        if value in classes:

            return int(
                encoder.transform(
                    [value]
                )[0]
            )

        # Defensive final fallback only when the model does not
        # contain a generic Regional Hub category.
        return int(
            encoder.transform(
                [classes[0]]
            )[0]
        )

    def predict_worst_case_delay(
        self,
        origin: str,
        destination: str,
        transport_mode: str,
        leg_type: str = "Global_Freight",
        condition_flag: str = "Clear",
        nlp_score: float = 0.0
    ) -> Dict[str, Any]:

        mode_key = (
            transport_mode or "road"
        ).lower().strip()

        # Mission Control:
        # Keep the ML input inside the expected threat range.
        try:
            nlp_score = float(nlp_score)

        except (
            TypeError,
            ValueError
        ):
            nlp_score = 0.0

        if not np.isfinite(nlp_score):
            nlp_score = 0.0

        nlp_score = min(
            1.0,
            max(
                0.0,
                nlp_score
            )
        )

        if not self.is_trained:

            return self._fallback_prediction(
                mode_key,
                "Deterministic Operational Prior (Engine Warming)"
            )

        try:

            feat_origin = self._encode_feature(
                origin,
                "Origin_Node"
            )

            feat_dest = self._encode_feature(
                destination,
                "Destination_Node"
            )

            feat_mode = self._encode_feature(
                mode_key,
                "Transport_Mode"
            )

            feat_leg = self._encode_feature(
                leg_type,
                "Leg_Type"
            )

            feat_cond = self._encode_feature(
                condition_flag,
                "Condition_Flag"
            )

            X_input = pd.DataFrame([
                {
                    "Leg_Type": feat_leg,
                    "Origin_Node": feat_origin,
                    "Destination_Node": feat_dest,
                    "Transport_Mode": feat_mode,
                    "Condition_Flag": feat_cond,
                    "NLP_Severity_Score": nlp_score
                }
            ])

            raw_prediction = float(
                self.model.predict(
                    X_input
                )[0]
            )

            if not np.isfinite(
                raw_prediction
            ):
                raise ValueError(
                    "Model returned a non-finite prediction."
                )

            profile = self.profiles.get(
                mode_key,
                {
                    "floor": 0.0,
                    "cap": 240.0
                }
            )

            floor = float(
                profile.get(
                    "floor",
                    0.0
                )
            )

            cap = float(
                profile.get(
                    "cap",
                    240.0
                )
            )

            calibrated_delay = min(
                max(
                    0.0,
                    raw_prediction
                ),
                cap
            )

            final_delay = max(
                calibrated_delay,
                floor
            )

            if calibrated_delay < floor:

                reason = (
                    f"Baseline Operational Friction "
                    f"(Historical p5: {floor}h)"
                )

            elif calibrated_delay < raw_prediction:

                reason = (
                    f"Operational Cap Applied "
                    f"(Historical p95 Bound: {cap}h)"
                )

            elif raw_prediction > floor:

                reason = (
                    "Quantile Disruption Prediction (p85 Risk)"
                )

            else:

                reason = "Optimal Flow"

            return {
                "raw_model_prediction": round(
                    raw_prediction,
                    2
                ),
                "calibrated_delay": round(
                    calibrated_delay,
                    2
                ),
                "baseline_systemic_friction": round(
                    floor,
                    2
                ),
                "final_delay_presented": round(
                    final_delay,
                    2
                ),
                "calibration_reason": reason,
                "p_quantile": 0.85,
                "is_defensible": True,
                "model_source": "PRODUCTION_MODEL"
            }

        except Exception as e:

            print(
                f"[P85 FALLBACK] "
                f"{origin} -> {destination}: {e}"
            )

            return self._fallback_prediction(
                mode_key,
                "ML inference failed; deterministic prior restored"
            )


class ContrastiveNLPEngine:
    """
    Production contrastive NLP threat engine.
    """

    def __init__(self, lazy_load=False):

        self._ready = False

        self.noise_floor = 0.04
        self.calibration_multiplier = 0.35

        if not lazy_load:
            self.warmup()

    def warmup(self):

        if self._ready:
            return

        print(
            "[NLP ENGINE] Starting warmup..."
        )

        try:

            from sentence_transformers import (
                SentenceTransformer,
                util
            )

            self.model = SentenceTransformer(
                "all-MiniLM-L6-v2"
            )

            self.util = util

            if not os.path.exists(
                NLP_ANCHORS_PATH
            ):
                raise FileNotFoundError(
                    "NLP anchor matrix not found."
                )

            # Mission Control:
            # Historical telemetry was produced on another device.
            # Always deserialize safely onto CPU.
            anchors = torch.load(
                NLP_ANCHORS_PATH,
                map_location=torch.device("cpu")
            )

            self.disaster_matrix = anchors[
                "disaster_matrix"
            ]

            self.safe_matrix = anchors[
                "safe_matrix"
            ]

            self._ready = True

            print(
                "NLP Brain: Loaded Historical Anchor Matrix."
            )

        except Exception as e:

            print(
                f"[NLP ENGINE] Warmup failed: {e}"
            )

            self._ready = False

    def get_semantic_score(
        self,
        news_text: str
    ) -> float:

        if not self._ready:
            return 0.0

        if (
            not news_text
            or len(news_text.strip()) < 5
        ):
            return 0.0

        chunks = [
            news_text[i:i + 256]
            for i in range(
                0,
                len(news_text),
                256
            )
        ]

        chunk_embeddings = self.model.encode(
            chunks,
            convert_to_tensor=True
        )

        disaster_scores = self.util.cos_sim(
            chunk_embeddings,
            self.disaster_matrix
        )

        safe_scores = self.util.cos_sim(
            chunk_embeddings,
            self.safe_matrix
        )

        # Mission Control:
        # Compare disaster and safe similarity on the SAME
        # text chunk. The previous implementation took the
        # maximum disaster score and maximum safe score
        # independently, which could compare two different
        # chunks and exaggerate/reverse the signal.
        d_matrix = (
            disaster_scores
            .cpu()
            .numpy()
        )

        s_matrix = (
            safe_scores
            .cpu()
            .numpy()
        )

        disaster_per_chunk = np.max(
            d_matrix,
            axis=1
        )

        safe_per_chunk = np.max(
            s_matrix,
            axis=1
        )

        margins = (
            disaster_per_chunk
            - safe_per_chunk
        )

        margin = float(
            np.max(margins)
        )

        if margin <= self.noise_floor:
            return 0.0

        return float(
            min(
                1.0,
                margin * self.calibration_multiplier
            )
        )


class CARFFilter:
    """
    Context-Aware Relevance Filter.

    Prevents a threat score from being carried into
    an unrelated transport mode.
    """

    def __init__(self):

        self.relevance_map = {

            "air": [
                "airport",
                "flight",
                "flights",
                "airspace",
                "aviation",
                "aircraft",
                "airline",
                "airlines",
                "cargo"
            ],

            "sea": [
                "port",
                "ports",
                "vessel",
                "vessels",
                "ship",
                "ships",
                "shipping",
                "canal",
                "canals",
                "ocean",
                "maritime",
                "dock",
                "docks",
                "harbor",
                "harbour",
                "container",
                "freight"
            ],

            "rail": [
                "rail",
                "rails",
                "railway",
                "track",
                "tracks",
                "locomotive",
                "station",
                "stations",
                "train",
                "trains"
            ],

            "road": [
                "highway",
                "highways",
                "truck",
                "trucks",
                "traffic",
                "bridge",
                "bridges",
                "road",
                "roads",
                "delivery",
                "deliveries"
            ]
        }

    def apply_filter(
        self,
        semantic_score: float,
        news_context: str,
        transport_mode: str
    ) -> float:

        try:
            semantic_score = float(
                semantic_score
            )

        except (
            TypeError,
            ValueError
        ):
            return 0.0

        if (
            not np.isfinite(semantic_score)
            or semantic_score <= 0
        ):
            return 0.0

        if not news_context:
            return 0.0

        mode = (
            transport_mode or ""
        ).lower().strip()

        if mode not in self.relevance_map:
            return min(
                1.0,
                semantic_score
            )

        import re

        normalized_text = re.sub(
            r"[^a-z0-9\s]",
            " ",
            news_context.lower()
        )

        news_words = set(
            normalized_text.split()
        )

        relevant_keywords = (
            self.relevance_map[mode]
        )

        is_relevant = any(
            keyword in news_words
            for keyword in relevant_keywords
        )

        if is_relevant:
            return min(
                1.0,
                semantic_score
            )

        return 0.0

    def max_pool_threats(
        self,
        scores: List[float]
    ) -> float:

        return (
            float(
                np.max(scores)
            )
            if scores
            else 0.0
        )