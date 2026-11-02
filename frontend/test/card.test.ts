import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { registered } from "../src/teamcity-card";
import type { TeamCityCard } from "../src/card";
import type { TeamCityBuildDetail } from "../src/build-detail";
import type { TeamCityCardConfig } from "../src/types";
import { SERVER, makeHass, type FakeHass } from "./fixtures";

const HISTORY = {
  builds: [
    {
      id: 101,
      number: "42",
      status: "SUCCESS",
      status_text: "Tests passed",
      branch_name: "main",
      start_date: "2026-11-01T09:00:00+00:00",
      finish_date: "2026-11-01T09:05:00+00:00",
      web_url: "https://tc.example.com/build/101",
      percentage_complete: null,
      state: "finished",
      triggered_by: "steve",
    },
  ],
};

async function settle(element: HTMLElement): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await (element as TeamCityCard).updateComplete;
  }
}

async function mount(
  config: Partial<TeamCityCardConfig>,
  hass: FakeHass = makeHass(),
): Promise<{ card: TeamCityCard; hass: FakeHass; root: ShadowRoot }> {
  const card = document.createElement("teamcity-card");
  card.setConfig({ type: "custom:teamcity-card", ...config });
  card.hass = hass;
  document.body.append(card);
  await settle(card);
  return { card, hass, root: card.shadowRoot! };
}

function click(root: ParentNode, selector: string): void {
  const element = root.querySelector<HTMLElement>(selector);
  if (!element) throw new Error(`No element for ${selector}`);
  element.click();
}

function text(root: ParentNode): string {
  return (root.textContent ?? "").replace(/\s+/g, " ");
}

beforeAll(async () => {
  await registered;
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("dashboard mode", () => {
  it("lists every build configuration with live state", async () => {
    const { root } = await mount({});
    const names = [...root.querySelectorAll(".row .name")].map((el) => el.textContent);
    expect(names).toEqual(["Build", "Deploy", "Build"]);
    expect(text(root)).toContain("1 running");
    expect(text(root)).toContain("1 queued");
    expect(text(root)).toContain("#43 · feature/x");
    expect(text(root)).toContain("Paused");
    expect(root.querySelector('[role="progressbar"]')?.getAttribute("aria-valuenow")).toBe("40");
  });

  it("filters by project and groups", async () => {
    const { root } = await mount({ scope: "projects", projects: ["App"], group_by_project: true });
    expect(root.querySelectorAll(".row")).toHaveLength(2);
    expect(root.querySelector(".group-name")?.textContent).toBe("App");
  });

  it("triggers a build without confirmation", async () => {
    const { root, hass } = await mount({});
    click(root, 'button[title="Run Deploy"]');
    expect(hass.callService).toHaveBeenCalledWith("teamcity", "trigger_build", {
      device_id: "device-app_deploy",
    });
  });

  it("asks before cancelling and only cancels on confirm", async () => {
    const { card, root, hass } = await mount({});
    click(root, 'button[title="Cancel Build #43"]');
    await settle(card);
    expect(text(root)).toContain("Cancel Build #43?");
    click(root, ".dialog button:not(.confirm)");
    await settle(card);
    expect(root.querySelector(".dialog")).toBeNull();
    expect(hass.callService).not.toHaveBeenCalled();

    click(root, 'button[title="Cancel queued build 201 of Build"]');
    await settle(card);
    click(root, ".dialog .confirm");
    await settle(card);
    expect(hass.callService).toHaveBeenCalledWith("teamcity", "cancel_build", {
      config_entry_id: "entry-1",
      build_id: 201,
    });
  });

  it("confirms pausing but unpauses immediately", async () => {
    const { card, root, hass } = await mount({});
    click(root, 'button[title="Unpause Deploy"]');
    expect(hass.callService).toHaveBeenCalledWith("teamcity", "set_paused", {
      device_id: "device-app_deploy",
      paused: false,
    });

    click(root, 'button[title="Pause Build"]');
    await settle(card);
    expect(hass.callService).toHaveBeenCalledTimes(1);
    click(root, ".dialog .confirm");
    await settle(card);
    expect(hass.callService).toHaveBeenLastCalledWith("teamcity", "set_paused", {
      device_id: "device-app_build",
      paused: true,
    });
  });

  it("hides cancel and pause controls when configured", async () => {
    const { root } = await mount({ show_cancel: false, show_pause: false });
    expect(root.querySelector('button[title^="Cancel"]')).toBeNull();
    expect(root.querySelector('button[title^="Pause"]')).toBeNull();
    expect(root.querySelector('button[title^="Run"]')).not.toBeNull();
  });

  it("shows action failures", async () => {
    const hass = makeHass();
    hass.callService.mockRejectedValueOnce({ message: "TeamCity said no" });
    const { card, root } = await mount({}, hass);
    click(root, 'button[title="Run Deploy"]');
    await settle(card);
    expect(root.querySelector('[role="alert"]')?.textContent).toContain("TeamCity said no");
  });

  it("explains when no server is set up", async () => {
    const hass = makeHass();
    hass.callWS.mockResolvedValueOnce({ servers: [] });
    const { root } = await mount({}, hass);
    expect(text(root)).toContain("No TeamCity server is set up");
  });

  it("re-renders only when a watched entity changes", async () => {
    const { card, hass } = await mount({});
    let renders = 0;
    const original = card["render"].bind(card);
    card["render"] = () => {
      renders++;
      return original();
    };
    card.hass = { ...hass, states: { ...hass.states, "sun.sun": undefined } };
    await settle(card);
    expect(renders).toBe(0);

    const states = { ...hass.states };
    states["switch.lib_build_paused"] = { ...states["switch.lib_build_paused"]!, state: "on" };
    card.hass = { ...hass, states };
    await settle(card);
    expect(renders).toBe(1);
  });
});

describe("console mode", () => {
  it("loads history, changes and log for the latest build when expanded", async () => {
    const hass = makeHass(SERVER, {
      "teamcity/build_history": HISTORY,
      "teamcity/build_changes": {
        changes: [
          { id: 1, version: "abcdef123456", username: "steve", date: null, comment: "Fix it\nmore", web_url: null },
        ],
      },
      "teamcity/build_log": { lines: ["step 1", "done"] },
      "teamcity/agents": { agents: [] },
    });
    const { card, root } = await mount({ mode: "console", history_count: 5 }, hass);
    click(root, 'button[title="Show details"]');
    await settle(card);
    const detail = root.querySelector<TeamCityBuildDetail>("teamcity-build-detail")!;
    await settle(detail);

    const detailText = text(detail.shadowRoot!);
    expect(detailText).toContain("#42");
    expect(detailText).toContain("Fix it");
    expect(detailText).not.toContain("more");
    expect(detail.shadowRoot!.querySelector(".log")?.textContent).toBe("step 1\ndone");
    const log = detail.shadowRoot!.querySelector(".log")!;
    expect(log.scrollTop).toBe(log.scrollHeight);
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({ type: "teamcity/build_history", count: 5 }),
    );
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({ type: "teamcity/build_log", build_id: 101, lines: 100 }),
    );
  });

  it("does not request logs the user may not view", async () => {
    const hass = makeHass(
      { ...SERVER, can_view_logs: false },
      { "teamcity/build_history": HISTORY, "teamcity/build_changes": { changes: [] } },
    );
    const { card, root } = await mount({ mode: "console", console_sections: ["history", "changes", "log"] }, hass);
    click(root, 'button[title="Show details"]');
    await settle(card);
    const detail = root.querySelector<TeamCityBuildDetail>("teamcity-build-detail")!;
    await settle(detail);
    expect(detail.shadowRoot!.querySelector(".log")).toBeNull();
    expect(hass.callWS).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: "teamcity/build_log" }),
    );
  });

  it("shows agents when enabled", async () => {
    const hass = makeHass(SERVER, {
      "teamcity/agents": {
        agents: [
          {
            id: 1,
            name: "agent-1",
            connected: true,
            enabled: true,
            authorized: true,
            running_build: { id: 103, build_type_id: "App_Build", number: "43", web_url: null },
          },
        ],
      },
    });
    const { root } = await mount({ mode: "console" }, hass);
    const agents = root.querySelector("teamcity-agents")!;
    await settle(agents);
    expect(text(agents.shadowRoot!)).toContain("agent-1");
    expect(text(agents.shadowRoot!)).toContain("Build #43");
  });
});

describe("tile mode", () => {
  it("shows one build configuration with a menu for pause and cancel", async () => {
    const { card, root, hass } = await mount({ mode: "tile", build_type: "App_Build" });
    expect(root.querySelectorAll(".tile")).toHaveLength(1);
    expect(text(root)).toContain("#42");
    expect(root.querySelector('button[title^="Cancel"]')).toBeNull();

    click(root, 'button[title="More actions"]');
    await settle(card);
    const items = [...root.querySelectorAll(".menu-item")].map((el) => text(el).trim());
    expect(items).toEqual(["Pause", "Cancel running build #43", "Cancel queued build 201"]);

    click(root, ".menu-item:nth-child(2)");
    await settle(card);
    click(root, ".dialog .confirm");
    await settle(card);
    expect(hass.callService).toHaveBeenCalledWith("teamcity", "cancel_build", {
      config_entry_id: "entry-1",
      build_id: 103,
    });
  });

  it("detailed style shows the recent build strip and inline controls", async () => {
    const hass = makeHass(SERVER, { "teamcity/build_history": HISTORY });
    const { root } = await mount({ mode: "tile", build_type: "App_Build", tile_style: "detailed" }, hass);
    const strip = root.querySelector("teamcity-build-strip")!;
    await settle(strip);
    expect(strip.shadowRoot!.querySelectorAll(".block")).toHaveLength(1);
    expect(root.querySelector('button[title="Cancel Build #43"]')).not.toBeNull();
    expect(root.querySelector('button[title="Pause Build"]')).not.toBeNull();
    expect(root.querySelector('button[title="More actions"]')).toBeNull();
    expect(hass.callWS).toHaveBeenCalledWith(
      expect.objectContaining({ type: "teamcity/build_history", count: 5 }),
    );
  });

  it("reports an unknown build configuration", async () => {
    const { root } = await mount({ mode: "tile", build_type: "Gone" });
    expect(text(root)).toContain("Build configuration Gone was not found");
  });
});

describe("registration", () => {
  it("defines every element and lists the card in the picker", () => {
    for (const name of ["teamcity-card", "teamcity-card-editor", "teamcity-agents", "teamcity-build-detail", "teamcity-build-strip"]) {
      expect(customElements.get(name), name).toBeDefined();
    }
    expect(window.customCards?.map((card) => card.type)).toContain("teamcity-card");
  });
});
