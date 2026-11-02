# HA-TeamCity

Home Assistant integration for JetBrains TeamCity, installable through [HACS](https://hacs.xyz). It includes a dashboard card for watching and managing builds.

It polls a TeamCity server every 60 seconds, or every 10 seconds while any build is running or queued, and shows each build configuration as a device.

## Installation

### HACS

1. In HACS, open the menu (⋮) → **Custom repositories**.
2. Add `https://github.com/steveharsant/HA-TeamCity` with category **Integration**.
3. Install **TeamCity** and restart Home Assistant.

HACS installs the zip attached to a GitHub release, which contains the built card.

### Manual

Download `teamcity.zip` from the [latest release](https://github.com/steveharsant/HA-TeamCity/releases/latest), extract it into `config/custom_components/teamcity/`, and restart. Copying `custom_components/teamcity` straight from the repository gives you the integration without the card, because the card is only built when a release is made (see [Development](#development)).

## Configuration

1. In TeamCity, open your profile → **Access Tokens** and create a token. The token sees what its user sees. For the trigger, cancel and pause controls to work, its user needs the *Run build*, *Cancel build* and *Pause/activate build configuration* permissions.
2. In Home Assistant go to **Settings → Devices & services → Add integration → TeamCity**.
3. Enter the server URL (e.g. `https://teamcity.example.com`) and the token. Turn off **Verify SSL certificate** only for servers with self-signed certificates.

The integration's **Configure** dialog has two options:

- **Build configurations**: by default every build configuration the token can see is added. Pick some to limit it. Devices for configurations you deselect, or that are deleted in TeamCity, are removed when the integration reloads. New build configurations are picked up automatically when nothing is selected.
- **Allow non-admins to view build logs**: off by default. Build logs can contain sensitive output, so the card only shows them to Home Assistant administrators unless you turn this on.

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
| `binary_sensor.…_state` | On while a build of this configuration is running on any branch. Attributes: number queued, queued build IDs, and each running build's ID, number, branch, % complete and URL |
| `button.…_trigger_build` | Queues a build of the default branch |
| `switch.…_paused` | On while the build configuration is paused in TeamCity; toggling it pauses or unpauses |

## Actions

These can be used in automations and scripts, and are what the card calls.

| Action | Fields |
|---|---|
| `teamcity.trigger_build` | `device_id`: a build configuration device |
| `teamcity.set_paused` | `device_id`: a build configuration device; `paused`: `true` or `false` |
| `teamcity.cancel_build` | `config_entry_id`: the TeamCity server; `build_id`: a running or queued build's ID (from the State sensor's attributes); `comment` (optional) |

Cancelling a build that has already finished fails with an error that says so.

## Dashboard card

The integration loads the card into Home Assistant itself, so you don't need to add a dashboard resource. Add it from the card picker (search for **TeamCity**) and set it up in the visual editor, or in YAML:

```yaml
type: custom:teamcity-card
mode: console            # dashboard | console | tile
scope: projects          # all | projects | build_types
projects: [Shop]
group_by_project: true
show_cancel: true
show_pause: true
console_sections: [history, changes, log, agents]
history_count: 10
log_lines: 100
```

| Option | Default | Description |
|---|---|---|
| `mode` | `dashboard` | `dashboard`: every build configuration with status, running progress, the queue and a Run button. `console`: the dashboard plus expandable detail per configuration and a server-wide agent list. `tile`: a single build configuration. |
| `title` | server name | Card title. In tile mode it replaces the build configuration's name. |
| `entry_id` | first server | Which TeamCity server to show, when more than one is set up. |
| `scope` | `all` | Which build configurations to show: `all`, those in `projects` (project IDs), or those in `build_types` (build configuration IDs). |
| `group_by_project` | `false` | Group rows under project headings. |
| `build_type` | (none) | Required in tile mode: the build configuration ID. |
| `tile_style` | `compact` | `compact`: status, last build and Run button, with pause and cancel in a ⋮ menu. `detailed`: adds a strip of the last 5 builds, the branch and status text, and puts pause and cancel inline. |
| `show_cancel` | `true` | Show buttons to cancel running and queued builds. |
| `show_pause` | `true` | Show pause and unpause buttons. |
| `console_sections` | all four | Which console detail to show: `history` (recent builds on any branch), `changes` (commits in the selected build), `log` (end of the selected build's log), `agents`. |
| `history_count` | `10` | Builds in the console history (1–100). |
| `log_lines` | `100` | Log lines in the console (1–1000). |

The card asks for confirmation before it cancels a build or pauses a configuration. Run and unpause act straight away.

`show_cancel` and `show_pause` only hide the controls on that card. Any user who can call the actions above can still cancel and pause builds. Build logs are the one thing the integration restricts by user, through the option described in [Configuration](#configuration).

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

The integration is in `custom_components/teamcity` and the card's source is in `frontend/` (TypeScript and Lit, bundled with Rollup).

```bash
# Integration
uv venv -p 3.13 .venv
uv pip install -p .venv -r requirements_test.txt ruff
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest

# Card
cd frontend
npm ci
npm run lint && npm run typecheck && npm test
npm run build    # writes custom_components/teamcity/frontend/teamcity-card.js
```

The built card is not committed. Without it, the integration still works and logs an error that the card is missing.

### Releasing

1. Bump `version` in both `custom_components/teamcity/manifest.json` and `frontend/package.json`.
2. Push a matching tag, e.g. `git tag v0.2.0 && git push origin v0.2.0`.

The **Release** workflow checks that the tag matches both versions, builds and tests the card, and attaches `teamcity.zip` (the integration plus the built card) to a new GitHub release. HACS installs from that zip.
