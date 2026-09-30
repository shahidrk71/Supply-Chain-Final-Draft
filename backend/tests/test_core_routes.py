import pytest

from backend.engine.scenario_manager import ScenarioManager
from backend.engine.multimodal_network import create_multimodal_network


def test_suez_scenario_has_mode_and_delay():
    mgr = ScenarioManager()
    scenario = mgr.activate_scenario("SUEZ_BLOCK")
    assert scenario["mode"] == "sea"
    assert scenario["delay_hours"] > 0
    active = mgr.get_active_disruptions()
    assert active["CHOKE-SUEZ"]["mode"] == "sea"


def test_network_is_directed_and_nonempty():
    graph = create_multimodal_network()
    assert graph.is_directed()
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() > 0
