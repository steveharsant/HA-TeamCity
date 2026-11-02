import { vi } from "vitest";
import type { BuildTypeInfo, HassEntity, HomeAssistant, ServerInfo } from "../src/types";

export function buildTypeInfo(
  id: string,
  name: string,
  projectId: string,
  projectName = projectId,
): BuildTypeInfo {
  const slug = id.toLowerCase();
  return {
    id,
    name,
    project_id: projectId,
    project_name: projectName,
    web_url: `https://tc.example.com/buildConfiguration/${id}`,
    device_id: `device-${slug}`,
    entities: {
      last_build_status: `sensor.${slug}_last_build_status`,
      last_build_finished: `sensor.${slug}_last_build_finished`,
      state: `binary_sensor.${slug}_state`,
      status: `binary_sensor.${slug}_status`,
      trigger_build: `button.${slug}_trigger_build`,
      paused: `switch.${slug}_paused`,
    },
  };
}

export const SERVER: ServerInfo = {
  entry_id: "entry-1",
  title: "TeamCity (tc.example.com)",
  can_view_logs: true,
  build_types: [
    buildTypeInfo("App_Build", "Build", "App"),
    buildTypeInfo("App_Deploy", "Deploy", "App"),
    buildTypeInfo("Lib_Build", "Build", "Lib"),
  ],
};

function entity(entityId: string, state: string, attributes: Record<string, unknown> = {}): HassEntity {
  return { entity_id: entityId, state, attributes, last_changed: "2026-11-01T00:00:00Z" };
}

export function makeStates(): Record<string, HassEntity> {
  const states: Record<string, HassEntity> = {};
  const add = (item: HassEntity) => {
    states[item.entity_id] = item;
  };
  add(
    entity("sensor.app_build_last_build_status", "success", {
      build_number: "42",
      branch: "main",
      web_url: "https://tc.example.com/build/101",
      status_text: "Tests passed: 10",
    }),
  );
  add(entity("sensor.app_build_last_build_finished", "2026-11-01T09:05:00+00:00"));
  add(
    entity("binary_sensor.app_build_state", "on", {
      queued: 1,
      queued_build_ids: [201],
      builds: [
        {
          build_id: 103,
          build_number: "43",
          branch: "feature/x",
          percentage_complete: 40,
          web_url: "https://tc.example.com/build/103",
        },
      ],
    }),
  );
  add(entity("switch.app_build_paused", "off"));
  add(entity("sensor.app_deploy_last_build_status", "failure", { build_number: "7" }));
  add(entity("sensor.app_deploy_last_build_finished", "unknown"));
  add(entity("binary_sensor.app_deploy_state", "off", { queued: 0, queued_build_ids: [], builds: [] }));
  add(entity("switch.app_deploy_paused", "on"));
  add(entity("sensor.lib_build_last_build_status", "unknown"));
  add(entity("binary_sensor.lib_build_state", "off", { queued: 0, queued_build_ids: [], builds: [] }));
  add(entity("switch.lib_build_paused", "off"));
  return states;
}

export interface FakeHass extends HomeAssistant {
  callService: ReturnType<typeof vi.fn<HomeAssistant["callService"]>>;
  callWS: ReturnType<typeof vi.fn<(message: Record<string, unknown>) => Promise<unknown>>> &
    HomeAssistant["callWS"];
}

export function makeHass(
  server: ServerInfo = SERVER,
  wsResponses: Record<string, unknown> = {},
): FakeHass {
  const callWS = vi.fn((message: Record<string, unknown>) => {
    const type = String(message.type);
    if (type === "teamcity/servers") {
      return Promise.resolve({ servers: [server] });
    }
    if (type in wsResponses) {
      return Promise.resolve(wsResponses[type]);
    }
    return Promise.reject(new Error(`Unexpected ${type}`));
  });
  return {
    states: makeStates(),
    language: "en",
    locale: { language: "en" },
    user: { is_admin: true },
    callService: vi.fn<HomeAssistant["callService"]>(() => Promise.resolve(undefined)),
    callWS: callWS as FakeHass["callWS"],
  };
}
