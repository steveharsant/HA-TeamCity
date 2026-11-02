import { LitElement, css, html, type TemplateResult } from "lit";
import { errorMessage, fetchServers } from "./api";
import { DEFAULT_HISTORY_COUNT, DEFAULT_LOG_LINES, selectServer } from "./config";
import {
  CONSOLE_SECTIONS,
  type ConsoleSection,
  type HomeAssistant,
  type Mode,
  type ServerInfo,
  type TeamCityCardConfig,
} from "./types";

interface SelectOption {
  value: string;
  label: string;
}

interface FormSchema {
  name: keyof TeamCityCardConfig;
  required?: boolean;
  selector: Record<string, unknown>;
}

const MODE_OPTIONS: SelectOption[] = [
  { value: "dashboard", label: "Build dashboard" },
  { value: "console", label: "Management console" },
  { value: "tile", label: "Single build configuration tile" },
];
const SCOPE_OPTIONS: SelectOption[] = [
  { value: "all", label: "All build configurations" },
  { value: "projects", label: "Chosen projects" },
  { value: "build_types", label: "Chosen build configurations" },
];
const TILE_STYLE_OPTIONS: SelectOption[] = [
  { value: "compact", label: "Compact" },
  { value: "detailed", label: "Detailed" },
];
const SECTION_LABELS: Record<ConsoleSection, string> = {
  history: "Recent build history",
  changes: "Changes in a build",
  log: "Build log tail",
  agents: "Agents",
};
const LABELS: Record<string, string> = {
  title: "Title (optional)",
  mode: "Mode",
  entry_id: "TeamCity server",
  scope: "Show",
  projects: "Projects",
  build_types: "Build configurations",
  group_by_project: "Group by project",
  build_type: "Build configuration",
  tile_style: "Tile style",
  show_cancel: "Show cancel buttons",
  show_pause: "Show pause buttons",
  console_sections: "Console sections",
  history_count: "Builds in history",
  log_lines: "Log lines",
};

const select = (options: SelectOption[], multiple = false) => ({
  select: { options, multiple, mode: multiple ? "list" : "dropdown" },
});

export function editorSchema(
  config: TeamCityCardConfig,
  servers: ServerInfo[],
): FormSchema[] {
  const mode: Mode = config.mode ?? "dashboard";
  const server = selectServer(servers, config.entry_id);
  const buildTypes = server?.build_types ?? [];
  const schema: FormSchema[] = [
    { name: "title", selector: { text: {} } },
    { name: "mode", required: true, selector: select(MODE_OPTIONS) },
  ];
  if (servers.length > 1) {
    schema.push({
      name: "entry_id",
      selector: select(servers.map((item) => ({ value: item.entry_id, label: item.title }))),
    });
  }
  if (mode === "tile") {
    schema.push(
      {
        name: "build_type",
        required: true,
        selector: select(
          buildTypes.map((item) => ({
            value: item.id,
            label: `${item.project_name} / ${item.name}`,
          })),
        ),
      },
      { name: "tile_style", selector: select(TILE_STYLE_OPTIONS) },
    );
  } else {
    schema.push({ name: "scope", selector: select(SCOPE_OPTIONS) });
    if (config.scope === "projects") {
      const projects = new Map(buildTypes.map((item) => [item.project_id, item.project_name]));
      schema.push({
        name: "projects",
        selector: select(
          [...projects].map(([value, label]) => ({ value, label })),
          true,
        ),
      });
    }
    if (config.scope === "build_types") {
      schema.push({
        name: "build_types",
        selector: select(
          buildTypes.map((item) => ({
            value: item.id,
            label: `${item.project_name} / ${item.name}`,
          })),
          true,
        ),
      });
    }
    schema.push({ name: "group_by_project", selector: { boolean: {} } });
  }
  schema.push(
    { name: "show_cancel", selector: { boolean: {} } },
    { name: "show_pause", selector: { boolean: {} } },
  );
  if (mode === "console") {
    schema.push(
      {
        name: "console_sections",
        selector: select(
          CONSOLE_SECTIONS.map((value) => ({ value, label: SECTION_LABELS[value] })),
          true,
        ),
      },
      { name: "history_count", selector: { number: { min: 1, max: 100, mode: "box" } } },
      { name: "log_lines", selector: { number: { min: 1, max: 1000, mode: "box" } } },
    );
  }
  return schema;
}

/** Fill in defaults so the form shows what the card will actually do. */
function formData(config: TeamCityCardConfig): TeamCityCardConfig {
  return {
    mode: "dashboard",
    scope: "all",
    tile_style: "compact",
    group_by_project: false,
    show_cancel: true,
    show_pause: true,
    console_sections: [...CONSOLE_SECTIONS],
    history_count: DEFAULT_HISTORY_COUNT,
    log_lines: DEFAULT_LOG_LINES,
    ...config,
  };
}

export class TeamCityCardEditor extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
    _servers: { state: true },
    _error: { state: true },
  };

  declare hass: HomeAssistant | undefined;
  declare private _config: TeamCityCardConfig | undefined;
  declare private _servers: ServerInfo[] | undefined;
  declare private _error: string | undefined;

  private _serversRequested = false;

  setConfig(config: TeamCityCardConfig): void {
    this._config = config;
  }

  protected override willUpdate(): void {
    if (this.hass && !this._serversRequested) {
      this._serversRequested = true;
      fetchServers(this.hass).then(
        (servers) => {
          this._servers = servers;
        },
        (error: unknown) => {
          this._error = errorMessage(error);
        },
      );
    }
  }

  protected override render(): TemplateResult {
    if (!this._config || !this.hass) {
      return html``;
    }
    return html`
      ${this._error ? html`<div class="error">Could not load TeamCity servers: ${this._error}</div>` : ""}
      <ha-form
        .hass=${this.hass}
        .data=${formData(this._config)}
        .schema=${editorSchema(this._config, this._servers ?? [])}
        .computeLabel=${(schema: FormSchema) => LABELS[schema.name] ?? schema.name}
        @value-changed=${(event: CustomEvent<{ value: TeamCityCardConfig }>) => {
          this.valueChanged(event.detail.value);
        }}
      ></ha-form>
    `;
  }

  private valueChanged(value: TeamCityCardConfig): void {
    const config: Record<string, unknown> = { type: "custom:teamcity-card" };
    for (const [key, item] of Object.entries(value)) {
      if (item !== undefined && item !== "") {
        config[key] = item;
      }
    }
    this._config = config as unknown as TeamCityCardConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      }),
    );
  }

  static override styles = css`
    .error {
      color: var(--error-color, #db4437);
      margin-bottom: 8px;
    }
  `;
}


declare global {
  interface HTMLElementTagNameMap {
    "teamcity-card-editor": TeamCityCardEditor;
  }
}
