import type {
  BuildTypeInfo,
  BuildTypeState,
  HassEntity,
  HomeAssistant,
  RunningBuild,
} from "./types";

const STATUSES = new Set(["success", "failure", "unknown"]);
const UNAVAILABLE = new Set(["unavailable", "unknown"]);

function stringAttribute(entity: HassEntity | undefined, name: string): string | null {
  const value = entity?.attributes[name];
  return typeof value === "string" ? value : null;
}

function isRunningBuild(value: unknown): value is RunningBuild {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { build_id?: unknown }).build_id === "number"
  );
}

export function readBuildTypeState(
  hass: HomeAssistant,
  info: BuildTypeInfo,
): BuildTypeState {
  const entity = (key: keyof BuildTypeInfo["entities"]): HassEntity | undefined => {
    const entityId = info.entities[key];
    return entityId ? hass.states[entityId] : undefined;
  };
  const status = entity("last_build_status");
  const finished = entity("last_build_finished");
  const runningEntity = entity("state");
  const paused = entity("paused");

  const builds = runningEntity?.attributes.builds;
  const queued = runningEntity?.attributes.queued_build_ids;

  return {
    info,
    status:
      status && STATUSES.has(status.state)
        ? (status.state as BuildTypeState["status"])
        : null,
    lastBuildNumber: stringAttribute(status, "build_number"),
    lastBuildBranch: stringAttribute(status, "branch"),
    lastBuildUrl: stringAttribute(status, "web_url"),
    lastBuildStatusText: stringAttribute(status, "status_text"),
    lastFinished: finished && !UNAVAILABLE.has(finished.state) ? finished.state : null,
    running: Array.isArray(builds) ? builds.filter(isRunningBuild) : [],
    queuedBuildIds: Array.isArray(queued)
      ? queued.filter((id): id is number => typeof id === "number")
      : [],
    paused: paused?.state === "on",
    available: status !== undefined && status.state !== "unavailable",
  };
}

/** Entity ids whose changes should re-render the card. */
export function watchedEntityIds(buildTypes: BuildTypeInfo[]): string[] {
  return buildTypes.flatMap((buildType) => Object.values(buildType.entities));
}
