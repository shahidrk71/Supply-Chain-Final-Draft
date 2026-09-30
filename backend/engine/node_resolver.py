import json
import os
from typing import Dict, Any


class NodeResolver:
    """
    Supplychainer Unified Node Resolver.

    Resolves city/hub identifiers into the split graph's
    physical_id:mode entry node.
    """

    def __init__(
        self,
        locations_path: str = None,
        hubs_path: str = None
    ):

        if not locations_path:

            locations_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "data",
                "canonical_locations.json"
            )

        if not hubs_path:

            hubs_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "data",
                "canonical_hubs.json"
            )

        self.location_map = {}

        if os.path.exists(
            locations_path
        ):

            with open(
                locations_path,
                "r"
            ) as f:

                self.location_map = json.load(
                    f
                )

        self.hubs = []

        if os.path.exists(
            hubs_path
        ):

            with open(
                hubs_path,
                "r"
            ) as f:

                self.hubs = json.load(
                    f
                )

    def resolve_node_to_entry_point(
        self,
        location_or_id: str
    ) -> Dict[str, Any]:

        if not location_or_id:

            return {
                "id": None,
                "error":
                    "Location or hub ID is required."
            }

        original = (
            str(
                location_or_id
            ).strip()
        )

        physical_id = None

        # Mission Control:
        # Direct canonical hub ID lookup.
        current_hub = next(
            (
                h
                for h in self.hubs
                if h["id"].lower()
                == original.lower()
            ),
            None
        )

        # City-level lookup.
        city_key = next(
            (
                key
                for key in self.location_map
                if key.lower()
                == original.lower()
            ),
            None
        )

        if city_key:

            physical_id = (
                self.location_map[
                    city_key
                ].get("road")
            )

            if not physical_id:

                values = list(
                    self.location_map[
                        city_key
                    ].values()
                )

                if values:
                    physical_id = values[0]

        elif current_hub:

            physical_id = (
                current_hub["id"]
            )

        if not physical_id:

            return {
                "id": None,
                "error":
                    f"Entry point unavailable for {original}"
            }

        target_hub = next(
            (
                h
                for h in self.hubs
                if h["id"] == physical_id
            ),
            None
        )

        if not target_hub:

            return {
                "id": None,
                "error":
                    f"Physical Hub mapping corrupted "
                    f"for {physical_id}"
            }

        modes = target_hub.get(
            "modes",
            []
        )

        if not modes:

            return {
                "id": None,
                "error":
                    f"No transport modes configured "
                    f"for {physical_id}"
            }

        entry_mode = (
            "road"
            if "road" in modes
            else modes[0]
        )

        return {
            "id":
                f"{physical_id}:{entry_mode}"
        }

    def resolve_node(
        self,
        location_or_id: str,
        mode: str = "any"
    ) -> str:

        result = (
            self.resolve_node_to_entry_point(
                location_or_id
            )
        )

        return result.get(
            "id"
        )