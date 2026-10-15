import pytest
from control_plane.apps.fleet.range_parser import expand_host_range


def test_expand_single_host():
    assert expand_host_range("server1.domain.com") == ["server1.domain.com"]


def test_expand_simple_range():
    assert expand_host_range("compute-[01:05].internal") == [
        "compute-01.internal",
        "compute-02.internal",
        "compute-03.internal",
        "compute-04.internal",
        "compute-05.internal",
    ]


def test_expand_unpadded_range():
    assert expand_host_range("node-[1:3]") == ["node-1", "node-2", "node-3"]


def test_expand_multiple_comma_separated():
    assert expand_host_range("node-[1:2], gpu-[08:09], single-host") == [
        "node-1",
        "node-2",
        "gpu-08",
        "gpu-09",
        "single-host",
    ]


def test_expand_duplicate_filtering():
    assert expand_host_range("node-1, node-[1:2]") == ["node-1", "node-2"]


def test_expand_invalid_bounds():
    with pytest.raises(ValueError, match="Invalid range bounds"):
        expand_host_range("compute-[10:05]")


def test_expand_empty_or_invalid_inputs():
    assert expand_host_range("") == []
    assert expand_host_range(None) == []
