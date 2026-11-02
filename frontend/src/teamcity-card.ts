import { TeamCityAgents } from "./agents";
import { TeamCityBuildDetail } from "./build-detail";
import { TeamCityBuildStrip } from "./build-strip";
import { TeamCityCard } from "./card";
import { TeamCityCardEditor } from "./editor";

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

declare global {
  interface Window {
    customCards?: CustomCardEntry[];
  }
}

const ELEMENTS: [string, CustomElementConstructor][] = [
  ["teamcity-agents", TeamCityAgents],
  ["teamcity-build-detail", TeamCityBuildDetail],
  ["teamcity-build-strip", TeamCityBuildStrip],
  ["teamcity-card-editor", TeamCityCardEditor],
  ["teamcity-card", TeamCityCard],
];

/**
 * Home Assistant swaps window.customElements for a scoped-registry polyfill while it
 * boots. Elements defined before that land in the native registry, where the dashboard
 * can't see them, so wait until Home Assistant's own root element is registered.
 */
async function homeAssistantReady(): Promise<void> {
  if (!document.querySelector("home-assistant")) {
    return;
  }
  while (!window.customElements.get("home-assistant")) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

export const registered: Promise<void> = homeAssistantReady().then(() => {
  for (const [name, element] of ELEMENTS) {
    if (!window.customElements.get(name)) {
      window.customElements.define(name, element);
    }
  }
  window.customCards ??= [];
  window.customCards.push({
    type: "teamcity-card",
    name: "TeamCity",
    description:
      "Build dashboard, management console or single build configuration tile for TeamCity.",
    preview: true,
    documentationURL: "https://github.com/steveharsant/HA-TeamCity",
  });
});
