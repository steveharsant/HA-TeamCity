import type { Agent, Build, Change, HomeAssistant, ServerInfo } from "./types";

export async function fetchServers(hass: HomeAssistant): Promise<ServerInfo[]> {
  const result = await hass.callWS<{ servers: ServerInfo[] }>({ type: "teamcity/servers" });
  return result.servers;
}

export async function fetchBuildHistory(
  hass: HomeAssistant,
  entryId: string,
  buildTypeId: string,
  count: number,
): Promise<Build[]> {
  const result = await hass.callWS<{ builds: Build[] }>({
    type: "teamcity/build_history",
    entry_id: entryId,
    build_type_id: buildTypeId,
    count,
  });
  return result.builds;
}

export async function fetchBuildChanges(
  hass: HomeAssistant,
  entryId: string,
  buildId: number,
): Promise<Change[]> {
  const result = await hass.callWS<{ changes: Change[] }>({
    type: "teamcity/build_changes",
    entry_id: entryId,
    build_id: buildId,
  });
  return result.changes;
}

export async function fetchBuildLog(
  hass: HomeAssistant,
  entryId: string,
  buildId: number,
  lines: number,
): Promise<string[]> {
  const result = await hass.callWS<{ lines: string[] }>({
    type: "teamcity/build_log",
    entry_id: entryId,
    build_id: buildId,
    lines,
  });
  return result.lines;
}

export async function fetchAgents(hass: HomeAssistant, entryId: string): Promise<Agent[]> {
  const result = await hass.callWS<{ agents: Agent[] }>({
    type: "teamcity/agents",
    entry_id: entryId,
  });
  return result.agents;
}

export async function triggerBuild(hass: HomeAssistant, deviceId: string): Promise<void> {
  await hass.callService("teamcity", "trigger_build", { device_id: deviceId });
}

export async function setPaused(
  hass: HomeAssistant,
  deviceId: string,
  paused: boolean,
): Promise<void> {
  await hass.callService("teamcity", "set_paused", { device_id: deviceId, paused });
}

export async function cancelBuild(
  hass: HomeAssistant,
  entryId: string,
  buildId: number,
): Promise<void> {
  await hass.callService("teamcity", "cancel_build", {
    config_entry_id: entryId,
    build_id: buildId,
  });
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "object" && error !== null && "message" in error) {
    return String(error.message);
  }
  return String(error);
}
