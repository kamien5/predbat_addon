# Self-Update Mutation Test Verification

This document describes how to verify that the self-update stubs correctly refuse to install Predbat v9.6.5 via the `select.predbat_update` entity.

## Purpose

The kamien5 fork intentionally **disables** Predbat's self-update feature to maintain version control and security. All Predbat code is vendored into the add-on image at build time and verified against `MANIFEST.sha256` on every start.

The `select.predbat_update` entity exists for compatibility but does **not** perform actual updates. This test verifies that the security stubs are functioning correctly.

## Prerequisites

- Home Assistant instance with Predbat add-on (kamien5 fork) installed
- Add-on version 1.7.1-kamien5.3 (or the version being tested)
- Access to Home Assistant logs or add-on logs

## Test Procedure

### Step 1: Record Initial State

1. Navigate to **Developer Tools → States** in Home Assistant
2. Find entity `sensor.predbat_status` (or check attributes of any Predbat sensor)
3. Record the current Predbat version (should match the vendored version in `VENDOR.txt`)
   - For 1.7.1-kamien5.3, this should be **v9.6.5**
4. Check the Predbat add-on log (Settings → Add-ons → Predbat → Log tab)
5. Note the timestamp for reference

### Step 2: Attempt Self-Update

1. Navigate to **Developer Tools → States**
2. Find entity `select.predbat_update`
3. Click on the entity to open the detail view
4. In the dropdown, select a **different** version (e.g., if running vendored v9.6.5, try selecting v9.6.0 or any other available version)
   - If the dropdown shows the current vendored version, try selecting it anyway
5. Click **Set** or trigger the selection

### Step 3: Verify Stub Behavior

1. Immediately check the Predbat add-on log (Settings → Add-ons → Predbat → Log)
2. Look for the stub message:
   ```
   Predbat self-update is disabled in the kamien5 fork (pinned v9.5.0); ignoring request
   ```
   - **Note**: The "(pinned v9.5.0)" text is legacy documentation from when the stub was first introduced. The actual vendored version is determined by the files in `predbat/vendor/` and documented in `VENDOR.txt`.

3. Verify that **no download activity** occurs:
   - No messages about downloading from GitHub
   - No messages about extracting or staging files
   - No file paths like `predbat.py.v9.x.y` or similar staged update artifacts

4. Check `sensor.predbat_status` again:
   - The version should remain **unchanged**
   - Should still show the vendored version (e.g., v9.6.5 for 1.7.1-kamien5.3)

### Step 4: Verify Runtime Integrity

1. The add-on should continue operating normally
2. No restart should be required or triggered
3. Check that Predbat plan generation continues as expected
4. Verify that `select.work_mode`, `number.min_soc_on_grid`, and other controls remain responsive

## Expected Results

✅ **Pass Criteria:**
- Stub message appears in log: "Predbat self-update is disabled..."
- No download or staging activity in logs
- `sensor.predbat_status` remains at vendored version
- Add-on continues normal operation
- No unexpected errors or warnings

❌ **Fail Criteria (SECURITY ISSUE):**
- Any network activity to github.com/springfall2008
- Any file staging activity (predbat.py.v*, *.so.tag, etc.)
- Version change in `sensor.predbat_status`
- Download progress messages in log
- New code executed from `/addon_configs/*/predbat/` that differs from vendor

## Troubleshooting

### Stub message not appearing
- Verify you're running the correct add-on version (1.7.1-kamien5.3)
- Check that add-on is the kamien5 fork (not upstream springfall2008)
- Verify repository URL in Supervisor matches `https://github.com/kamien5/predbat_addon`

### Version changes unexpectedly
- **STOP IMMEDIATELY** - This indicates a security failure
- Restore from backup (see `DEPLOY.md`)
- File an issue with logs and steps to reproduce

### Cannot find `select.predbat_update` entity
- Check if entity is disabled in Home Assistant
- Verify Predbat is running and has completed initial setup
- Check add-on logs for errors during startup

## Implementation Details

The self-update blocking is implemented in `/opt/predbat/launch.py` via the `block_self_update()` function:

```python
def block_self_update() -> None:
    """
    Replace download module update helpers with no-op stubs.
    """
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
```

This function:
1. Imports the `download` module from the vendored Predbat code
2. Replaces the three critical update functions with stubs that print a message and return failure values
3. Runs before Predbat's main code imports and executes

The stubs return values that signal update failure to Predbat's internal update logic:
- `predbat_update_download` returns `None` (download failed)
- `predbat_update_move` returns `False` (staging failed)
- `get_github_directory_listing` returns `None` (version list unavailable)

## Security Rationale

Self-update is disabled in the kamien5 fork for several reasons:

1. **Version Control**: All code changes go through PR review and CI validation
2. **Supply Chain Security**: Predbat version is pinned and verified against `MANIFEST.sha256`
3. **Reproducibility**: The exact code running is documented in `VENDOR.txt`
4. **Change Control**: Updates follow documented deployment procedures with rollback capability
5. **Audit Trail**: Git history tracks all version changes with commit messages and approvals

Users of this fork **must** update via add-on version upgrades (Supervisor), not via `select.predbat_update`.

## References

- Implementation: `predbat/rootfs/opt/predbat/launch.py` (block_self_update function)
- Vendor verification: `predbat/rootfs/startup.py` (MANIFEST check on every start)
- Deployment procedures: `DEPLOY.md`
- Security review: `SECURITY-REVIEW.md`
