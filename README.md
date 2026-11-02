# HA-TeamCity

Home Assistant integration for JetBrains TeamCity, installable through [HACS](https://hacs.xyz).

It polls a TeamCity server every 60 seconds and shows each build configuration as a device, with a button to trigger a new build.

## Installation

### HACS

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/steveharsant/HA-TeamCity` with category **Integration**.
3. Install **TeamCity** and restart Home Assistant.

### Manual

Copy `custom_components/teamcity` into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. In TeamCity, open your profile → **Access Tokens** and create a token. The token sees what its user sees; it needs the *Run build* permission if you want the trigger buttons to work.
2. In Home Assistant go to **Settings → Devices & services → Add integration → TeamCity**.
3. Enter the server URL (e.g. `https://teamcity.example.com`) and the token. Turn off **Verify SSL certificate** only for servers with self-signed certificates.

By default every build configuration the token can see is added. To limit this, open the integration's **Configure** dialog and pick the build configurations you want. Devices for configurations you deselect, or that are deleted in TeamCity, are removed when the integration reloads. New build configurations are picked up automatically when no selection is set.

If the token expires or is revoked, Home Assistant asks you to re-authenticate.

## Entities

**Server device**

| Entity | Description |
|---|---|
| `sensor.<server>_queued_builds` | Builds waiting in the queue |
| `sensor.<server>_running_builds` | Builds currently running |

**One device per build configuration** (named `<project> / <build configuration>`)

| Entity | Description |
|---|---|
| `sensor.…_last_build_status` | `success`, `failure` or `unknown` for the last finished build on the default branch. Attributes: build id, build number, status text, branch, start time, web URL |
| `sensor.…_last_build_finished` | When that build finished |
| `binary_sensor.…_status` | On when the last finished default-branch build failed |
| `binary_sensor.…_state` | On while a build of this configuration is running on any branch. Attributes: number queued, and each running build's number, branch, % complete and URL |
| `button.…_trigger_build` | Queues a build of the default branch |

## Example automation

```yaml
automation:
  - alias: Flash the lights when the deploy breaks
    triggers:
      - trigger: state
        entity_id: binary_sensor.app_deploy_status
        to: "on"
    actions:
      - action: light.turn_on
        target:
          entity_id: light.office
        data:
          color_name: red
          flash: short
```

## Development

```bash
uv venv -p 3.13 .venv
uv pip install -p .venv -r requirements_test.txt ruff
.venv/bin/ruff check .
.venv/bin/pytest
```
