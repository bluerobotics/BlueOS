from unittest.mock import mock_open, patch

import pytest

from ..general import CpuType, get_cpu_type

CPUINFO_TEMPLATE = """processor	: 0
BogoMIPS	: 108.00
Features	: fp asimd evtstrm crc32 cpuid
CPU implementer	: 0x41
CPU architecture: 8

Hardware	: BCM2835
Revision	: d03141
Serial		: 10000000abcdef01
Model		: {model}
"""


@pytest.mark.parametrize(
    "model,expected_cpu_type",
    [
        ("Raspberry Pi 3 Model B Rev 1.2", CpuType.PI3),
        ("Raspberry Pi 4 Model B Rev 1.4", CpuType.PI4),
        ("Raspberry Pi 5 Model B Rev 1.0", CpuType.PI5),
        ("Raspberry Pi Compute Module 4 Rev 1.1", CpuType.PI4),
        ("Raspberry Pi Compute Module 5 Rev 1.0", CpuType.PI5),
        ("Some Other Board", CpuType.Other),
    ],
)
def test_get_cpu_type(model: str, expected_cpu_type: CpuType) -> None:
    cpuinfo = CPUINFO_TEMPLATE.format(model=model)
    get_cpu_type.cache_clear()
    with patch("builtins.open", mock_open(read_data=cpuinfo)):
        assert get_cpu_type() == expected_cpu_type
    get_cpu_type.cache_clear()
