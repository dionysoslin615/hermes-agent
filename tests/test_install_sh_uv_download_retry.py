from pathlib import Path


def test_uv_installer_download_has_bounded_network_retry():
    script = (Path(__file__).parents[1] / "scripts" / "install.sh").read_text()
    assert (
        'curl --retry 4 --retry-all-errors --retry-delay 2 -LsSf '
        'https://astral.sh/uv/install.sh' in script
    )
