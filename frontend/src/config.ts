import {
  CONSOLE_SECTIONS,
  type BuildTypeInfo,
  type ResolvedConfig,
  type ServerInfo,
  type TeamCityCardConfig,
} from "./types";

export const DEFAULT_HISTORY_COUNT = 10;
export const DEFAULT_LOG_LINES = 100;
export const TILE_HISTORY_COUNT = 5;

export function resolveConfig(config: TeamCityCardConfig): ResolvedConfig {
  const mode = config.mode ?? "dashboard";
  if (mode === "tile" && !config.build_type) {
    throw new Error("Tile mode needs a build_type");
  }
  return {
    title: config.title,
    mode,
    entryId: config.entry_id,
    scope: config.scope ?? "all",
    projects: config.projects ?? [],
    buildTypes: config.build_types ?? [],
    groupByProject: config.group_by_project ?? false,
    buildType: config.build_type,
    tileStyle: config.tile_style ?? "compact",
    showCancel: config.show_cancel ?? true,
    showPause: config.show_pause ?? true,
    consoleSections: config.console_sections ?? [...CONSOLE_SECTIONS],
    historyCount: config.history_count ?? DEFAULT_HISTORY_COUNT,
    logLines: config.log_lines ?? DEFAULT_LOG_LINES,
  };
}

export function selectServer(
  servers: ServerInfo[],
  entryId: string | undefined,
): ServerInfo | undefined {
  return entryId ? servers.find((server) => server.entry_id === entryId) : servers[0];
}

/** Build configurations the card should show, in server order (project, then name). */
export function selectBuildTypes(
  server: ServerInfo,
  config: ResolvedConfig,
): BuildTypeInfo[] {
  if (config.mode === "tile") {
    return server.build_types.filter((buildType) => buildType.id === config.buildType);
  }
  switch (config.scope) {
    case "all":
      return server.build_types;
    case "projects":
      return server.build_types.filter((buildType) =>
        config.projects.includes(buildType.project_id),
      );
    case "build_types":
      return server.build_types.filter((buildType) =>
        config.buildTypes.includes(buildType.id),
      );
  }
}

export function groupByProject<T extends { info: BuildTypeInfo }>(
  items: T[],
): { projectId: string; projectName: string; items: T[] }[] {
  const groups = new Map<string, { projectId: string; projectName: string; items: T[] }>();
  for (const item of items) {
    const { project_id: projectId, project_name: projectName } = item.info;
    let group = groups.get(projectId);
    if (!group) {
      group = { projectId, projectName, items: [] };
      groups.set(projectId, group);
    }
    group.items.push(item);
  }
  return [...groups.values()];
}
