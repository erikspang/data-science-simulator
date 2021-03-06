__author__ = "Cameron Summers"

"""
Classes for simulation specific code.
"""

import multiprocessing
import copy
import datetime
import pandas as pd


class SimulationComponent(object):
    """
    A class with abstract and convenience methods for use in the simulation.
    """

    def get_state(self):
        raise NotImplementedError

    def update(self, time, **kwargs):
        raise NotImplementedError

    def get_time_delta_minutes(self, end_time):
        tdelta = end_time - self.time
        return tdelta.minutes


class SimulationState(object):
    """
    A class for holding the state of the simulation at any given time.
    """

    def __init__(self, patient_state, controller_state):
        """
        Parameters
        ----------
        patient_state: VirtualPatientState
        controller_state
        """

        self.patient_state = patient_state
        self.controller_state = controller_state

    def __repr__(self):

        return "BG: {:.2f}, IOB: {:.2f} Temp Basal: {}".format(
            self.patient_state.bg,
            self.patient_state.iob,
            self.patient_state.pump_state.temp_basal_rate,
        )


class Simulation(multiprocessing.Process):
    """
    A class that organizes the elements of the simulation through time and
    tracks results. Separation of Concerns: This class owns time tracking and
    member objects should be using minimal time logic, e.g. indexing historical
    or future information.
    """

    def __init__(
        self,
        time,
        duration_hrs,
        simulation_config,
        virtual_patient,
        controller,
        multiprocess=False,
    ):

        # To enable multiprocessing
        super().__init__()
        self.queue = multiprocessing.Queue()
        self.multiprocess = multiprocess

        self.simulation_config = simulation_config

        self.start_time = copy.deepcopy(time)
        self.time = time

        self.duration_hrs = duration_hrs
        self.virtual_patient = virtual_patient
        self.controller = controller

        self.simulation_results = dict()

        # Get things setup for t=0
        self.init()

    def init(self):
        """
        Initialize the simulation
        """

        # Set any temp basals at t=0
        self.controller.update(self.time, virtual_patient=self.virtual_patient)

        # Setup steady state basal and t0 glucose
        self.virtual_patient.init()

        # Establish prediction based on events at t0 and init above
        self.virtual_patient.predict()

        # Store info at t=0
        self.store_state()

    def update(self, time):
        """
        Main feedback loop between patient and controller.

        Parameters
        ----------
        time: datetime
        """
        # Set patient state at time from prediction at time - 1
        self.virtual_patient.update_from_prediction(time)

        # Get and set on patient the next action from controller,
        #   e.g. temp basal, at time
        self.controller.update(time, virtual_patient=self.virtual_patient)

        # Update patient prediction and member states
        self.virtual_patient.update(time)

    def step(self):
        """
        Move the simulation time forward one step, which is 5 minutes.
        """
        next_time = self.time + datetime.timedelta(minutes=5)

        self.time = next_time
        self.update(next_time)

    def run(self):
        """
        Run the simulation until it's finished.
        """
        while not self.is_finished():
            self.step()
            self.store_state()

        if self.multiprocess:
            self.queue.put(self.get_results_df())

        return self.simulation_results

    def store_state(self):
        """
        Store the current state of the simulation in the results.
        """
        self.simulation_results[self.time] = SimulationState(
            patient_state=self.virtual_patient.get_state(),
            controller_state=self.controller.get_state(),
        )

    def is_finished(self):
        """
        Determines if the simulation has finished running.

        Returns
        -------
        bool:
            True if the simulation has passed the specified length
        """

        seconds_passed = (self.time - self.start_time).total_seconds()
        hours_frac_passed = seconds_passed / 3600.0

        return hours_frac_passed >= self.duration_hrs

    def get_results_df(self):
        """
        Get results as a dataframe object.

        Returns
        -------
        pd.DataFrame
            The time series result of the simulation
        """

        data = [
            {
                "time": time,
                "bg": simulation_state.patient_state.bg,
                "bg_sensor": simulation_state.patient_state.sensor_bg,
                "iob": simulation_state.patient_state.iob,
                "temp_basal": simulation_state.patient_state.pump_state.get_temp_basal_rate_value(
                    default=None
                ),
                "temp_basal_zeros": simulation_state.patient_state.pump_state.get_temp_basal_rate_value(
                    default=0
                ),
                "sbr": simulation_state.patient_state.pump_state.scheduled_basal_rate.value,
                "cir": simulation_state.patient_state.cir,
                "isf": simulation_state.patient_state.isf,
            }
            for time, simulation_state in self.simulation_results.items()
        ]

        df = pd.DataFrame(data)
        df.set_index("time")
        return df


class SettingSchedule24Hr(SimulationComponent):
    """
    A class for settings schedules on a 24 hour cycle.
    """

    def __init__(self, time, name, start_times, values, duration_minutes):
        """
        Parameters
        ----------
        time: datetime
            Current time

        name: str
            Setting name

        start_times: list
            List of datetime.time objects

        values: list
            List of objects

        duration_minutes: list
            List of ints
        """

        self.time = time
        self.name = name

        # All the same length
        assert (
            len(start_times) + len(values) + len(duration_minutes)
            == len(start_times) * 3
        )

        self.schedule = {}
        for start_time, value, duration_minutes in zip(
            start_times, values, duration_minutes
        ):

            start_datetime = datetime.datetime.combine(
                datetime.datetime.today(), start_time
            )
            end_datetime = (
                start_datetime
                + datetime.timedelta(minutes=duration_minutes)
                - datetime.timedelta(seconds=1)
            )
            end_time = end_datetime.time()
            self.schedule[(start_time, end_time)] = value

    def get_state(self):
        """
        Get the value object at the current time, e.g. carb ratio or target range

        Returns
        -------
        object
            The object at the current time
        """

        for (start_time, end_time), value in self.schedule.items():
            current_time = self.time.time()
            if start_time <= current_time <= end_time:
                return value

        raise Exception("Could not find setting for time {}".format(self.time))

    def validate_schedule(self):
        """
        Ensure there are no overlapping segments,
         units are consistent,
         datetimes have no gaps for 24 hrs
        """
        raise NotImplementedError

    def update(self, time, **kwargs):
        """
        Set the new time.

        Parameters
        ----------
        time: datetime
        """

        self.time = time


class EventTimeline(object):
    """
    A class for insulin/carb/etc. events
    """

    def __init__(self, datetimes, events):

        self.events = pd.DataFrame({"date": datetimes, "event": events})

    def get_event(self, time):
        """
        Get the event at the given time. If no event, returns None

        Parameters
        ----------
        time: datetime
            Time to check for event

        Returns
        -------
        object
            The insulin/carb/etc. event or None
        """
        event = None

        event_mask = self.events["date"] == time
        if event_mask.any():
            event = self.events[event_mask]["event"].values[0]

        return event
