"""Virtual Horizon backend sensor package.

Pure Python, no Decky dependency: everything here is importable and testable
off-device.  ``backend/main.py`` wires these modules to the Decky runtime.
"""

from .adapters import IioSensor, discover
from .filter import OrientationFilter
from .settings import Settings
from .state import SensorPipeline, State

__all__ = [
    "IioSensor",
    "OrientationFilter",
    "SensorPipeline",
    "Settings",
    "State",
    "discover",
]
