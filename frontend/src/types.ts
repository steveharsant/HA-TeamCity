export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
}

export interface HomeAssistant {
  states: Record<string, HassEntity | undefined>;
  user?: { is_admin: boolean };
  locale?: { language: string };
  language: string;
  callService(
    domain: string,
    service: string,
    data: Record<string, unknown>,
  ): Promise<unknown>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
}

export const MODES = ["dashboard", "console", "tile"] as const;
export type Mode = (typeof MODES)[number];

export const SCOPES = ["all", "projects", "build_types"] as const;
export type Scope = (typeof SCOPES)[number];

export const TILE_STYLES = ["compact", "detailed"] as const;
export type TileStyle = (typeof TILE_STYLES)[number];

export const CONSOLE_SECTIONS = ["history", "changes", "log", "agents"] as const;
export type ConsoleSection = (typeof CONSOLE_SECTIONS)[number];

export interface TeamCityCardConfig {
  type: string;
  title?: string;
  mode?: Mode;
  entry_id?: string;
  scope?: Scope;
  projects?: string[];
  build_types?: string[];
  group_by_project?: boolean;
  build_type?: string;
  tile_style?: TileStyle;
  show_cancel?: boolean;
  show_pause?: boolean;
  console_sections?: ConsoleSection[];
  history_count?: number;
  log_lines?: number;
}

export interface ResolvedConfig {
  title: string | undefined;
  mode: Mode;
  entryId: string | undefined;
  scope: Scope;
  projects: string[];
  buildTypes: string[];
  groupByProject: boolean;
  buildType: string | undefined;
  tileStyle: TileStyle;
  showCancel: boolean;
  showPause: boolean;
  consoleSections: ConsoleSection[];
  historyCount: number;
  logLines: number;
}

export type EntityKey =
  | "last_build_status"
  | "last_build_finished"
  | "state"
  | "status"
  | "trigger_build"
  | "paused";

export interface BuildTypeInfo {
  id: string;
  name: string;
  project_id: string;
  project_name: string;
  web_url: string | null;
  device_id: string | null;
  entities: Partial<Record<EntityKey, string>>;
}

export interface ServerInfo {
  entry_id: string;
  title: string;
  can_view_logs: boolean;
  build_types: BuildTypeInfo[];
}

export interface Build {
  id: number;
  number: string | null;
  status: string | null;
  status_text: string | null;
  branch_name: string | null;
  start_date: string | null;
  finish_date: string | null;
  web_url: string | null;
  percentage_complete: number | null;
  state: string | null;
  triggered_by: string | null;
}

export interface Change {
  id: number;
  version: string | null;
  username: string | null;
  date: string | null;
  comment: string | null;
  web_url: string | null;
}

export interface Agent {
  id: number;
  name: string;
  connected: boolean;
  enabled: boolean;
  authorized: boolean;
  running_build: {
    id: number;
    build_type_id: string;
    number: string | null;
    web_url: string | null;
  } | null;
}

export interface RunningBuild {
  build_id: number;
  build_number: string | null;
  branch: string | null;
  percentage_complete: number | null;
  web_url: string | null;
}

/** Live state of one build configuration, read from its entities. */
export interface BuildTypeState {
  info: BuildTypeInfo;
  status: "success" | "failure" | "unknown" | null;
  lastBuildNumber: string | null;
  lastBuildBranch: string | null;
  lastBuildUrl: string | null;
  lastBuildStatusText: string | null;
  lastFinished: string | null;
  running: RunningBuild[];
  queuedBuildIds: number[];
  paused: boolean;
  available: boolean;
}
