import os
import datetime
import matplotlib.pyplot as plt

from tidepool_data_science_simulator.makedata.jaeb_data_sim_parser import JaebDataSimParser
from tidepool_data_science_simulator.models.pump import ContinuousInsulinPump
from tidepool_data_science_simulator.models.patient.virtual_patient import VirtualPatient
from tidepool_data_science_simulator.models.sensor import IdealSensor
from tidepool_data_science_simulator.models.controller import LoopController
from tidepool_data_science_simulator.models.simulation import Simulation
from tidepool_data_science_simulator.visualization.sim_viz import plot_sim_results

from tidepool_data_science_models.models.simple_metabolism_model import SimpleMetabolismModel


def run_replay(path_to_settings, path_to_time_series_data, t0=None):

    jaeb_parser = JaebDataSimParser(
        path_to_settings=path_to_settings,
        path_to_time_series_data=path_to_time_series_data
    )

    t0 = jaeb_parser.get_simulation_start_time()

    all_results = {}

    pump = ContinuousInsulinPump(
        time=t0,
        pump_config=jaeb_parser.get_pump_config()
    )

    sensor = IdealSensor(
        time=t0,
        sensor_config=jaeb_parser.get_sensor_config()
    )

    patient_config = jaeb_parser.get_patient_config()
    patient_config.recommendation_accept_prob = 1.0
    patient = VirtualPatient(
        time=t0,
        pump=pump,
        sensor=sensor,
        metabolism_model=SimpleMetabolismModel,
        patient_config=patient_config
    )

    controller = LoopController(
        time=t0,
        controller_config=jaeb_parser.get_controller_config()
    )

    sim = Simulation(
        time=t0,
        duration_hrs=24,
        virtual_patient=patient,
        controller=controller
    )

    sim.run()
    results_df = sim.get_results_df()
    sim_id = jaeb_parser.patient_id + "-" + str(jaeb_parser.report_num)
    all_results[sim_id] = results_df

    sim_end_date = t0 + datetime.timedelta(days=1)

    dates_to_plot = [date for date in patient_config.real_glucose.datetimes if t0 < date <= sim_end_date]
    gluc_to_plot = [patient_config.real_glucose.bg_values[i] for i in range(len(
        patient_config.real_glucose.bg_values)) if t0 < patient_config.real_glucose.datetimes[i] <= sim_end_date]
    plt.plot(dates_to_plot, gluc_to_plot)
    plt.show()
    plot_sim_results(all_results)


if __name__ == "__main__":
    parsed_data_folder = "../PHI-Jaeb-Data/"
    parsed_data_files = os.listdir(parsed_data_folder)

    time_series_files = []
    time_series_folder = ""
    for filename in parsed_data_files:
        if "data-summary" in filename:
            issue_report_settings_path = os.path.join(parsed_data_folder, filename)
        elif "time-series" in filename:
            time_series_files = os.listdir(parsed_data_folder + filename)
            time_series_folder = filename

    for filename in time_series_files[:1]:
        time_series_path = parsed_data_folder + time_series_folder + "/" + filename
        run_replay(path_to_settings=issue_report_settings_path, path_to_time_series_data=time_series_path)