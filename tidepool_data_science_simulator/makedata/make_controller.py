__author__ = "Cameron Summers"

from tidepool_data_science_simulator.models.simulation import CarbTimeline, BolusTimeline
from tidepool_data_science_simulator.makedata.scenario_parser import ControllerConfig

from tidepool_data_science_simulator.makedata.scenario_parser import ScenarioParserCSV


def get_canonical_controller(t0, controller_class):

    controller_settings = {
        "model": [360.0, 65],
        "momentum_data_interval": 15,
        "suspend_threshold": 70,
        "dynamic_carb_absorption_enabled": True,
        "retrospective_correction_integration_interval": True,
        "recency_interval": 15,
        "retrospective_correction_grouping_interval": 30,
        "rate_rounder": 0.05,
        "insulin_delay": 10,
        "carb_delay": 10,
        "default_absorption_times": [120.0, 180.0, 240.0],
        "max_basal_rate": 35,
        "max_bolus": 30,
        "retrospective_correction_enabled": True
    }
    controller_config = ControllerConfig(
        bolus_event_timeline=BolusTimeline(),
        carb_event_timeline=CarbTimeline(),
        controller_settings=controller_settings
    )

    controller = controller_class(t0, controller_config)

    return t0, controller