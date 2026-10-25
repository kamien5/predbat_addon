#!/usr/bin/env python3
"""
Launch Predbat with self-update disabled (kamien5 fork).

Runs from the image (/opt/predbat/launch.py). Working directory and sys.path
use CONFIG_DIR so hass.py and the freshly installed download.py are used.
block_self_update() must run before predbat is imported so that
`from download import predbat_update_download, ...` binds the stubs.
"""

from __future__ import annotations

import os
import runpy
import sys

CONFIG_DIR = os.environ.get("PREDBAT_CONFIG_DIR", "/config")

DISABLED_MESSAGE = (
    "Predbat self-update is disabled in the kamien5 fork "
    "(pinned v9.5.0); ignoring request"
)


def block_self_update() -> None:
    """
    Replace download module update helpers with no-op stubs.

    Import download from CONFIG_DIR (caller must put it on sys.path first).
    Stubs return the same failure/skip values as a failed network update so
    PredBat.download_predbat_version and import-time check_install paths
    cannot pull or install remote code.
    """
    # Late import: CONFIG_DIR must already be on sys.path (see main()).
    import download

    def predbat_update_download(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return None

    def predbat_update_move(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return False

    def get_github_directory_listing(*_args, **_kwargs):
        print(DISABLED_MESSAGE)
        return None

    download.predbat_update_download = predbat_update_download
    download.predbat_update_move = predbat_update_move
    download.get_github_directory_listing = get_github_directory_listing


def main() -> None:
    if not os.path.isdir(CONFIG_DIR):
        print("Error: CONFIG_DIR does not exist: {}".format(CONFIG_DIR))
        sys.exit(1)

    os.chdir(CONFIG_DIR)
    # Prefer CONFIG_DIR modules over anything else on the path.
    sys.path.insert(0, CONFIG_DIR)

    block_self_update()

    hass_path = os.path.join(CONFIG_DIR, "hass.py")
    if not os.path.isfile(hass_path):
        print("Error: hass.py not found in {}".format(CONFIG_DIR))
        sys.exit(1)

    # Mimic `python hass.py` without putting secrets on argv.
    sys.argv = [hass_path]
    runpy.run_path(hass_path, run_name="__main__")


if __name__ == "__main__":
    main()
