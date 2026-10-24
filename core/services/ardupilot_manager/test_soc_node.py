import pathlib

from autopilot_manager import soc_node_needs_alias


def test_soc_alias_is_only_added_when_the_plain_node_is_missing(tmp_path: pathlib.Path) -> None:
    assert not soc_node_needs_alias(tmp_path)

    (tmp_path / "soc@107c000000").mkdir()
    assert soc_node_needs_alias(tmp_path)

    (tmp_path / "soc").mkdir()
    assert not soc_node_needs_alias(tmp_path)
