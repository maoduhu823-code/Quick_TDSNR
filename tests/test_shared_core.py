from sipi_sparam_core import __version__ as core_version
from sipi_sparam_core.time_response import pulse_response_from_transfer
from sipi_sparam_core.topology import detect_topology


def test_required_shared_core_is_available():
    assert core_version == "0.1.0"
    assert callable(detect_topology)
    assert callable(pulse_response_from_transfer)

