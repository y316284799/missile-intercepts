"""
Ballistic missile classes.

Contents:
    Public classes:
        BallisticMissile
"""
#TODO: verify initial launch velocity less than Earth escape velocity

# Import packages
from collections import OrderedDict
from typing import Dict, Optional

import numpy as np

from missiles_abstract import Missile
# from kml_classes import KMLTrajectorySim
import geo_utils as geo
import utils as utl

# Get constants
constants = utl.get_constants()

# Define classes
class BallisticMissile(Missile):
    """Base class for missiles with a ballistic trajectory.
    
    Attributes:
        params: dict of user-defined parameter values
        LP_latlon_deg: tuple of launchpoint (latitude, longitude) in degrees
        AP_latlon_deg: tuple of aimpoint (latitutde, longitude) in degrees
        build_data: dict of static characteristics of ballistic missile
        trajectory_data: dict of missile position/orientation for each timestep
        kml_trajectory:

    Methods:
        build
        launch
        get_current_position
        get_current_orientation
        compute_initial_vertical_velocity
        compute_current_vertical_velocity
    """

    def __init__(self, params: Dict) -> None:
        """Instantiate BallisticMissile."""
        super(BallisticMissile, self).__init__(params)
        self.build_data = None
        self.trajectory_data = None
        self.kml_trajectory = None

    def build(self) -> None:
        """Compute static characteristics of ballistic missile:
            - Launchpoint distance to target (km)
            - Launchpoint bearing (deg)
            - Total time-to-target (seconds)
            - Horizontal velocity (km/s)
            - Initial vertical velocity (km/s)
            - Initial launch velocity (km/s)
            - Initial launch angle (degrees)
        """
        dist_to_target_km = self.compute_distance_to_target(self.LP_latlon_deg)
        time_to_target_sec = (
            dist_to_target_km / self.params['horizontal_velocity_km_sec']
        )
        initial_vertical_velocity_km_sec = self.compute_initial_vertical_velocity(
            time_to_target_sec
        )
        initial_launch_velocity_km_sec = self.compute_velocity(
            self.params['horizontal_velocity_km_sec'],
            initial_vertical_velocity_km_sec,
        )
        initial_launch_angle_deg = self.compute_altitude_angle(
            self.params['horizontal_velocity_km_sec'],
            initial_vertical_velocity_km_sec,
        )
        self.build_data = {
            'launchpoint_dist_to_target_km':dist_to_target_km,
            'launchpoint_bearing_deg':self.compute_bearing(self.LP_latlon_deg),
            'total_time_to_target_sec':time_to_target_sec,
            'horizontal_velocity_km_sec':self.params['horizontal_velocity_km_sec'],
            'initial_vertical_velocity_km_sec':initial_vertical_velocity_km_sec,
            'initial_launch_velocity_km_sec':initial_launch_velocity_km_sec,
            'initial_launch_angle_deg':initial_launch_angle_deg,
        }

    def launch(
        self,
        stoptime_sec: Optional[float] = None,
        timestep_sec: float = 1,
    ) -> None:
        """Record missile position (latitude, longitude, altitude) and orientation
        (heading, tilt, and roll) for each timestep from launch until impact.
        
        Arguments
            stoptime_sec: maximum time (seconds) for which to calculate missile
                position and orientation
            timestep_sec: timestep interval (seconds)
        """
        traj_dict = OrderedDict()
        if stoptime_sec is None:
            stoptime_sec = self.build_data['total_time_to_target_sec']
        for elapsed_time_sec in np.arange(0, stoptime_sec + timestep_sec, timestep_sec):
            position_dict = self.get_current_position(elapsed_time_sec)
            orientation_dict = self.get_current_orientation(elapsed_time_sec)
            traj_dict[elapsed_time_sec] = {**position_dict, **orientation_dict}
        self.trajectory_data = traj_dict

    def get_current_position(self, elapsed_time_sec: float) -> Dict:
        """Compute the current latitude/longitude (degrees) and altitude (km)
        of missile based on elapsed time since launch (seconds).

        Arguments
            elapsed_time_sec: elapsed time since launch (seconds)

        Returns
            dict containing lat_deg, lon_deg, and alt_km
        """
        dist_km = self.build_data['horizontal_velocity_km_sec'] * elapsed_time_sec
        current_latlon_deg = geo.determine_destination_coords(
            origin_lat_deg=self.LP_latlon_deg[0],
            origin_lon_deg=self.LP_latlon_deg[1],
            distance_km=dist_km,
            initial_bearing_deg=self.build_data['launchpoint_bearing_deg'],
        )
        # Integrate vertical velocity formula
        current_altitude_km = ( 
            self.build_data['initial_vertical_velocity_km_sec'] * elapsed_time_sec
            + (0.5 * constants['GRAVITY_ACCEL_KM_PER_S2'] * elapsed_time_sec**2)
        )
        return {
            'lat_deg':current_latlon_deg[0],
            'lon_deg':current_latlon_deg[1],
            'alt_km':current_altitude_km,
        }

    def get_current_orientation(self, elapsed_time_sec: float) -> Dict:
        """Compute the heading, tilt, and roll (degrees) for current position
        based on elapsed time since launch (seconds).
        Note: For version 0.1.0, COLLADA missile representations are
        assumed to be symmetrical, and roll is always set to 0 degrees.

        Arguments
            elapsed_time_sec: elapsed time since launch (seconds)

        Returns
            dict containing bearing_deg, tilt_deg, and roll_deg
        """
        position_dict = self.get_current_position(elapsed_time_sec)
        position_latlon_deg = (position_dict['lat_deg'], position_dict['lon_deg'])
        current_bearing_deg = self.compute_bearing(position_latlon_deg)
        current_tilt_deg = geo.rad_to_deg(
            geo.convert_trig_to_compass_angle(
                np.arctan2(
                    self.compute_current_vertical_velocity(elapsed_time_sec),
                    self.build_data['horizontal_velocity_km_sec'],
                )
            )
        )
        return {
            'bearing_deg':current_bearing_deg,
            'tilt_deg':current_tilt_deg,
            'roll_deg':0,
        }

    def compute_initial_vertical_velocity(self, time_to_target_sec: float) -> float:
        """Compute initial vertical velocity (km/s) at time of launch as 
        time-to-apogee (seconds) multiplied by gravitational acceleration (km/s^2).

        Arguments:
            time_to_target_sec: missile time-to-target (seconds)

        Returns:
            initial vertical velocity (km/s)
        """
        time_to_apogee_sec = time_to_target_sec * 0.5
        initial_vertical_velocity_km_sec = (
            time_to_apogee_sec * abs(constants['GRAVITY_ACCEL_KM_PER_S2'])
        )
        return initial_vertical_velocity_km_sec

    def compute_current_vertical_velocity(self, elapsed_time_sec: float) -> float:
        """Compute vertical velocity (km/s) given time since launch (seconds).
        
        Arguments:
            elapsed_time_sec: Elapsed time since launch (in seconds)

        Returns:
            current vertical velocity (km/s)
        """
        change_in_velocity = constants['GRAVITY_ACCEL_KM_PER_S2'] * elapsed_time_sec
        return (
            self.build_data['initial_vertical_velocity_km_sec'] 
            + change_in_velocity
        )

    # def create_kml_trajectory(self) -> None:
    #     """Convert missile trajectory to KML."""
    #     kml_trajectory_sim = KMLTrajectorySim(
    #         data=self.trajectory_data,
    #         collada_model_link=self.collada_model_link,
    #         collada_model_scale=self.collada_model_scale,
    #     )
    #     kml_trajectory_sim.create_trajectory()
    #     self.kml_trajectory = kml_trajectory_sim.kml

    #     self.intercept_ground_dist_from_TMAP_km = intercept_ground_dist_from_TMAP_km
    #     self.collada_model_link = collada_model_link
    #     self.collada_model_scale = collada_model_scale
    #     self.intercept_seconds_after_launch = None
    #     self.set_intercept_time()


    # def set_intercept_time(self) -> None:
    #     """Compute and set the time of intercept in seconds after launch, 
    #     given intercept distance from targeted missile aimpoint (TMAP)."""
    #     if self.intercept_ground_dist_from_TMAP_km is not None:
    #         self.intercept_seconds_after_launch = (
    #             (self.dist_to_target_km - self.intercept_ground_dist_from_TMAP_km)
    #             / self.horiz_vel_km_per_sec
    #         )
    #     else:
    #         self.intercept_seconds_after_launch = None