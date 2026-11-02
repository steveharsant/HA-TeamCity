import { describe, expect, it } from "vitest";
import { groupByProject, resolveConfig, selectBuildTypes, selectServer } from "../src/config";
import { editorSchema } from "../src/editor";
import { buildLabel, duration, relativeTime } from "../src/format";
import { readBuildTypeState, watchedEntityIds } from "../src/state";
import { SERVER, makeHass } from "./fixtures";

describe("resolveConfig", () => {
  it("applies defaults", () => {
    expect(resolveConfig({ type: "custom:teamcity-card" })).toMatchObject({
      mode: "dashboard",
      scope: "all",
      tileStyle: "compact",
      showCancel: true,
      showPause: true,
      consoleSections: ["history", "changes", "log", "agents"],
      historyCount: 10,
      logLines: 100,
    });
  });

  it("requires a build type in tile mode", () => {
    expect(() => resolveConfig({ type: "custom:teamcity-card", mode: "tile" })).toThrow(
      "Tile mode needs a build_type",
    );
  });
});

describe("selectBuildTypes", () => {
  const ids = (config: Parameters<typeof resolveConfig>[0]) =>
    selectBuildTypes(SERVER, resolveConfig(config)).map((item) => item.id);

  it("selects all, by project, by id, or the tile's build type", () => {
    expect(ids({ type: "t" })).toEqual(["App_Build", "App_Deploy", "Lib_Build"]);
    expect(ids({ type: "t", scope: "projects", projects: ["Lib"] })).toEqual(["Lib_Build"]);
    expect(ids({ type: "t", scope: "build_types", build_types: ["App_Deploy"] })).toEqual([
      "App_Deploy",
    ]);
    expect(ids({ type: "t", mode: "tile", build_type: "App_Build" })).toEqual(["App_Build"]);
  });

  it("picks the configured server or the first", () => {
    expect(selectServer([SERVER], undefined)).toBe(SERVER);
    expect(selectServer([SERVER], "other")).toBeUndefined();
  });

  it("groups by project preserving order", () => {
    const groups = groupByProject(SERVER.build_types.map((info) => ({ info })));
    expect(groups.map((group) => [group.projectId, group.items.length])).toEqual([
      ["App", 2],
      ["Lib", 1],
    ]);
  });
});

describe("readBuildTypeState", () => {
  it("reads status, running, queued and paused from entities", () => {
    const hass = makeHass();
    const [appBuild, appDeploy, libBuild] = SERVER.build_types.map((info) =>
      readBuildTypeState(hass, info),
    );
    expect(appBuild).toMatchObject({
      status: "success",
      lastBuildNumber: "42",
      lastFinished: "2026-11-01T09:05:00+00:00",
      queuedBuildIds: [201],
      paused: false,
      available: true,
    });
    expect(appBuild?.running.map((build) => build.build_id)).toEqual([103]);
    expect(appDeploy).toMatchObject({ status: "failure", lastFinished: null, paused: true });
    expect(libBuild).toMatchObject({ status: "unknown", lastBuildNumber: null });
  });

  it("marks missing entities unavailable", () => {
    const hass = makeHass();
    hass.states = {};
    const state = readBuildTypeState(hass, SERVER.build_types[0]!);
    expect(state).toMatchObject({ available: false, status: null, running: [] });
  });

  it("lists every entity to watch", () => {
    expect(watchedEntityIds([SERVER.build_types[0]!])).toHaveLength(6);
  });
});

describe("format", () => {
  it("formats relative time", () => {
    const now = Date.parse("2026-11-01T10:00:00Z");
    expect(relativeTime("2026-11-01T09:55:00Z", "en", now)).toBe("5 minutes ago");
    expect(relativeTime("2026-10-31T10:00:00Z", "en", now)).toBe("yesterday");
  });

  it("formats durations", () => {
    expect(duration("2026-11-01T09:00:00Z", "2026-11-01T09:00:42Z")).toBe("42s");
    expect(duration("2026-11-01T09:00:00Z", "2026-11-01T09:05:03Z")).toBe("5m 3s");
    expect(duration("2026-11-01T09:00:00Z", "2026-11-01T11:30:00Z")).toBe("2h 30m");
    expect(duration(null, "2026-11-01T11:30:00Z")).toBeNull();
  });

  it("labels builds by number, falling back to id", () => {
    expect(buildLabel("42", 1)).toBe("#42");
    expect(buildLabel(null, 7)).toBe("id 7");
  });
});

describe("editorSchema", () => {
  const names = (config: Parameters<typeof editorSchema>[0]) =>
    editorSchema(config, [SERVER]).map((item) => item.name);

  it("shows scope pickers only for the chosen scope", () => {
    expect(names({ type: "t" })).not.toContain("projects");
    expect(names({ type: "t", scope: "projects" })).toContain("projects");
    expect(names({ type: "t", scope: "build_types" })).toContain("build_types");
  });

  it("shows tile and console options only in their modes", () => {
    expect(names({ type: "t", mode: "tile" })).toEqual(
      expect.arrayContaining(["build_type", "tile_style"]),
    );
    expect(names({ type: "t", mode: "tile" })).not.toContain("scope");
    expect(names({ type: "t", mode: "console" })).toEqual(
      expect.arrayContaining(["console_sections", "history_count", "log_lines"]),
    );
    expect(names({ type: "t" })).not.toContain("console_sections");
  });

  it("offers the server picker only with several servers", () => {
    expect(names({ type: "t" })).not.toContain("entry_id");
    expect(
      editorSchema({ type: "t" }, [SERVER, { ...SERVER, entry_id: "entry-2" }]).map(
        (item) => item.name,
      ),
    ).toContain("entry_id");
  });
});
