import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { cancelBuild, errorMessage, fetchServers, setPaused, triggerBuild } from "./api";
import { groupByProject, resolveConfig, selectBuildTypes, selectServer } from "./config";
import { buildLabel, relativeTime } from "./format";
import { readBuildTypeState, watchedEntityIds } from "./state";
import { statusIcon } from "./status";
import { sharedStyles } from "./styles";
import type {
  BuildTypeInfo,
  BuildTypeState,
  HomeAssistant,
  ResolvedConfig,
  ServerInfo,
  TeamCityCardConfig,
} from "./types";

interface PendingConfirmation {
  message: string;
  confirmLabel: string;
  action: () => Promise<void>;
}

export class TeamCityCard extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
    _servers: { state: true },
    _loadError: { state: true },
    _actionError: { state: true },
    _busy: { state: true },
    _expanded: { state: true },
    _confirmation: { state: true },
    _menuOpen: { state: true },
  };

  declare hass: HomeAssistant | undefined;
  declare private _config: ResolvedConfig | undefined;
  declare private _servers: ServerInfo[] | undefined;
  declare private _loadError: string | undefined;
  declare private _actionError: string | undefined;
  declare private _busy: Set<string>;
  declare private _expanded: Set<string>;
  declare private _confirmation: PendingConfirmation | undefined;
  declare private _menuOpen: boolean;

  private _serversRequested = false;

  constructor() {
    super();
    this._busy = new Set();
    this._expanded = new Set();
    this._menuOpen = false;
  }

  static getConfigElement(): HTMLElement {
    return document.createElement("teamcity-card-editor");
  }

  static getStubConfig(): Partial<TeamCityCardConfig> {
    return { mode: "dashboard", scope: "all" };
  }

  setConfig(config: TeamCityCardConfig): void {
    this._config = resolveConfig(config);
  }

  getCardSize(): number {
    if (this._config?.mode === "tile") {
      return this._config.tileStyle === "detailed" ? 3 : 2;
    }
    return 1 + (this.visibleBuildTypes()?.length ?? 3);
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this._serversRequested = false;
    this.requestUpdate();
  }

  protected override shouldUpdate(changed: PropertyValues<this>): boolean {
    if (changed.size !== 1 || !changed.has("hass")) {
      return true;
    }
    const previous = changed.get("hass");
    const buildTypes = this.visibleBuildTypes();
    if (!previous || !this.hass || !buildTypes) {
      return true;
    }
    const states = this.hass.states;
    return watchedEntityIds(buildTypes).some(
      (entityId) => previous.states[entityId] !== states[entityId],
    );
  }

  protected override willUpdate(): void {
    if (this.hass && !this._serversRequested) {
      this._serversRequested = true;
      void this.loadServers(this.hass);
    }
  }

  private async loadServers(hass: HomeAssistant): Promise<void> {
    try {
      this._servers = await fetchServers(hass);
      this._loadError = undefined;
    } catch (error) {
      this._loadError = errorMessage(error);
    }
  }

  private server(): ServerInfo | undefined {
    return this._servers && this._config
      ? selectServer(this._servers, this._config.entryId)
      : undefined;
  }

  private visibleBuildTypes(): BuildTypeInfo[] | undefined {
    const server = this.server();
    return server && this._config ? selectBuildTypes(server, this._config) : undefined;
  }

  protected override render(): TemplateResult {
    const config = this._config;
    if (!config || !this.hass) {
      return html``;
    }
    return html`<ha-card>
      ${this.renderBody(config, this.hass)}
      ${this._actionError
        ? html`<div class="banner error" role="alert">
            <span>${this._actionError}</span>
            <button
              class="icon-button"
              title="Dismiss"
              @click=${() => {
                this._actionError = undefined;
              }}
            >
              <ha-icon icon="mdi:close"></ha-icon>
            </button>
          </div>`
        : nothing}
      ${this._confirmation ? this.renderConfirmation(this._confirmation) : nothing}
    </ha-card>`;
  }

  private renderBody(config: ResolvedConfig, hass: HomeAssistant): TemplateResult {
    if (this._loadError) {
      return html`<div class="message error">
        Could not load TeamCity servers: ${this._loadError}
      </div>`;
    }
    if (!this._servers) {
      return html`<div class="message muted">Loading…</div>`;
    }
    const server = this.server();
    if (!server) {
      return html`<div class="message error">
        ${config.entryId
          ? "The TeamCity server for this card is not set up or not loaded."
          : "No TeamCity server is set up. Add the TeamCity integration first."}
      </div>`;
    }
    const states = selectBuildTypes(server, config).map((info) =>
      readBuildTypeState(hass, info),
    );
    if (config.mode === "tile") {
      const [state] = states;
      return state
        ? this.renderTile(state, server, config, hass)
        : html`<div class="message error">
            Build configuration ${config.buildType ?? ""} was not found on ${server.title}.
          </div>`;
    }
    return this.renderList(states, server, config, hass);
  }

  private renderHeader(server: ServerInfo, config: ResolvedConfig, states: BuildTypeState[]) {
    const running = states.reduce((total, state) => total + state.running.length, 0);
    const queued = states.reduce((total, state) => total + state.queuedBuildIds.length, 0);
    return html`<div class="header">
      <div class="title ellipsis">${config.title ?? server.title}</div>
      <div class="summary muted">
        ${running ? html`<span>${String(running)} running</span>` : nothing}
        ${queued ? html`<span>${String(queued)} queued</span>` : nothing}
      </div>
    </div>`;
  }

  private renderList(
    states: BuildTypeState[],
    server: ServerInfo,
    config: ResolvedConfig,
    hass: HomeAssistant,
  ): TemplateResult {
    const rows = (items: BuildTypeState[], showProject: boolean) =>
      items.map((state) => this.renderRow(state, server, config, hass, showProject));
    return html`
      ${this.renderHeader(server, config, states)}
      <div class="list">
        ${states.length === 0
          ? html`<div class="message muted">No build configurations match this card.</div>`
          : config.groupByProject
            ? groupByProject(states).map(
                (group) => html`<div class="group">
                  <div class="group-name">${group.projectName}</div>
                  ${rows(group.items, false)}
                </div>`,
              )
            : rows(states, true)}
      </div>
      ${config.mode === "console" && config.consoleSections.includes("agents")
        ? html`<teamcity-agents
            class="section"
            .hass=${hass}
            .entryId=${server.entry_id}
            .buildTypeNames=${new Map(server.build_types.map((info) => [info.id, info.name]))}
            .refreshKey=${states.map((state) => state.running.length).join()}
          ></teamcity-agents>`
        : nothing}
    `;
  }

  private renderRow(
    state: BuildTypeState,
    server: ServerInfo,
    config: ResolvedConfig,
    hass: HomeAssistant,
    showProject: boolean,
  ): TemplateResult {
    const { info } = state;
    const expandable = config.mode === "console";
    const expanded = expandable && this._expanded.has(info.id);
    const language = hass.locale?.language ?? hass.language;
    const lastBuild = [
      showProject ? info.project_name : null,
      state.lastBuildNumber ? `#${state.lastBuildNumber}` : null,
      state.lastFinished ? relativeTime(state.lastFinished, language) : null,
    ].filter(Boolean);
    return html`<div class="row ${state.available ? "" : "unavailable"}">
      <div class="row-main">
        ${statusIcon(state.running.length ? "running" : state.paused ? "paused" : state.status)}
        <div class="names">
          ${info.web_url
            ? html`<a class="name ellipsis" href=${info.web_url} target="_blank" rel="noreferrer"
                >${info.name}</a
              >`
            : html`<span class="name ellipsis">${info.name}</span>`}
          <span class="muted ellipsis" title=${state.lastBuildStatusText ?? ""}
            >${lastBuild.join(" · ") || "No builds yet"}</span
          >
        </div>
        ${state.paused ? html`<span class="badge">Paused</span>` : nothing}
        <div class="actions">
          ${config.showPause ? this.renderPauseButton(state, hass) : nothing}
          ${this.renderRunButton(state, hass)}
          ${expandable
            ? html`<button
                class="icon-button"
                title=${expanded ? "Hide details" : "Show details"}
                aria-expanded=${expanded ? "true" : "false"}
                @click=${() => {
                  this.toggleExpanded(info.id);
                }}
              >
                <ha-icon .icon=${expanded ? "mdi:chevron-up" : "mdi:chevron-down"}></ha-icon>
              </button>`
            : nothing}
        </div>
      </div>
      ${this.renderActiveBuilds(state, server, config, hass)}
      ${expanded
        ? html`<teamcity-build-detail
            .hass=${hass}
            .entryId=${server.entry_id}
            .buildTypeId=${info.id}
            .sections=${config.consoleSections}
            .historyCount=${config.historyCount}
            .logLines=${config.logLines}
            .canViewLogs=${server.can_view_logs}
            .refreshKey=${refreshKey(state)}
          ></teamcity-build-detail>`
        : nothing}
    </div>`;
  }

  private renderActiveBuilds(
    state: BuildTypeState,
    server: ServerInfo,
    config: ResolvedConfig,
    hass: HomeAssistant,
  ): TemplateResult | typeof nothing {
    if (!state.running.length && !state.queuedBuildIds.length) {
      return nothing;
    }
    return html`<div class="active">
      ${state.running.map((build) => {
        const percent = build.percentage_complete ?? 0;
        const label = buildLabel(build.build_number, build.build_id);
        return html`<div class="running">
          <div class="progress-label muted">
            <span class="ellipsis"
              >${label}${build.branch ? html` · ${build.branch}` : nothing}</span
            >
            <span>${String(percent)}%</span>
          </div>
          <div
            class="progress"
            role="progressbar"
            aria-label="${state.info.name} ${label}"
            aria-valuenow=${percent}
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div class="progress-fill" style="width: ${String(percent)}%"></div>
          </div>
          ${config.showCancel
            ? this.renderCancelButton(server, hass, build.build_id, `${state.info.name} ${label}`)
            : nothing}
        </div>`;
      })}
      ${state.queuedBuildIds.length
        ? html`<div class="queued muted">
            <span>${String(state.queuedBuildIds.length)} queued</span>
            ${config.showCancel
              ? state.queuedBuildIds.map((buildId) =>
                  this.renderCancelButton(
                    server,
                    hass,
                    buildId,
                    `queued build ${String(buildId)} of ${state.info.name}`,
                    "mdi:close-circle-outline",
                  ),
                )
              : nothing}
          </div>`
        : nothing}
    </div>`;
  }

  private renderRunButton(state: BuildTypeState, hass: HomeAssistant): TemplateResult {
    const deviceId = state.info.device_id;
    const key = `run:${state.info.id}`;
    return html`<button
      class="icon-button primary"
      title="Run ${state.info.name}"
      ?disabled=${!deviceId || !state.available || this._busy.has(key)}
      @click=${() => {
        if (deviceId) void this.perform(key, () => triggerBuild(hass, deviceId));
      }}
    >
      <ha-icon icon="mdi:play"></ha-icon>
    </button>`;
  }

  private renderPauseButton(state: BuildTypeState, hass: HomeAssistant): TemplateResult {
    const deviceId = state.info.device_id;
    const key = `pause:${state.info.id}`;
    const pause = !state.paused;
    return html`<button
      class="icon-button"
      title="${pause ? "Pause" : "Unpause"} ${state.info.name}"
      ?disabled=${!deviceId || !state.available || this._busy.has(key)}
      @click=${() => {
        if (!deviceId) return;
        const action = () => setPaused(hass, deviceId, pause);
        if (pause) {
          this.confirm(`Pause ${state.info.name}? New builds won't start until it is unpaused.`, "Pause", key, action);
        } else {
          void this.perform(key, action);
        }
      }}
    >
      <ha-icon .icon=${pause ? "mdi:pause" : "mdi:play-pause"}></ha-icon>
    </button>`;
  }

  private renderCancelButton(
    server: ServerInfo,
    hass: HomeAssistant,
    buildId: number,
    description: string,
    icon = "mdi:stop",
  ): TemplateResult {
    const key = `cancel:${String(buildId)}`;
    return html`<button
      class="icon-button danger"
      title="Cancel ${description}"
      ?disabled=${this._busy.has(key)}
      @click=${() => {
        this.confirm(`Cancel ${description}?`, "Cancel build", key, () =>
          cancelBuild(hass, server.entry_id, buildId),
        );
      }}
    >
      <ha-icon .icon=${icon}></ha-icon>
    </button>`;
  }

  private renderTile(
    state: BuildTypeState,
    server: ServerInfo,
    config: ResolvedConfig,
    hass: HomeAssistant,
  ): TemplateResult {
    const { info } = state;
    const language = hass.locale?.language ?? hass.language;
    const detailed = config.tileStyle === "detailed";
    const subtitle = [
      state.lastBuildNumber ? `#${state.lastBuildNumber}` : null,
      detailed ? state.lastBuildBranch : null,
      state.lastFinished ? relativeTime(state.lastFinished, language) : null,
    ].filter(Boolean);
    const hasMenu = !detailed && (config.showPause || config.showCancel);
    return html`<div class="tile ${state.available ? "" : "unavailable"}">
      <div class="row-main">
        ${statusIcon(state.running.length ? "running" : state.paused ? "paused" : state.status)}
        <div class="names">
          ${info.web_url
            ? html`<a class="name ellipsis" href=${info.web_url} target="_blank" rel="noreferrer"
                >${config.title ?? info.name}</a
              >`
            : html`<span class="name ellipsis">${config.title ?? info.name}</span>`}
          <span class="muted ellipsis" title=${state.lastBuildStatusText ?? ""}
            >${subtitle.join(" · ") || "No builds yet"}</span
          >
        </div>
        ${state.paused ? html`<span class="badge">Paused</span>` : nothing}
        <div class="actions">
          ${detailed && config.showPause ? this.renderPauseButton(state, hass) : nothing}
          ${this.renderRunButton(state, hass)}
          ${hasMenu
            ? html`<button
                class="icon-button"
                title="More actions"
                aria-haspopup="true"
                aria-expanded=${this._menuOpen ? "true" : "false"}
                @click=${() => {
                  this._menuOpen = !this._menuOpen;
                }}
              >
                <ha-icon icon="mdi:dots-vertical"></ha-icon>
              </button>`
            : nothing}
        </div>
      </div>
      ${hasMenu && this._menuOpen ? this.renderTileMenu(state, server, config, hass) : nothing}
      ${detailed
        ? html`<div class="tile-detail">
            <teamcity-build-strip
              .hass=${hass}
              .entryId=${server.entry_id}
              .buildTypeId=${info.id}
              .refreshKey=${refreshKey(state)}
            ></teamcity-build-strip>
            ${state.lastBuildStatusText
              ? html`<span class="muted ellipsis">${state.lastBuildStatusText}</span>`
              : nothing}
          </div>`
        : nothing}
      ${detailed || state.running.length
        ? this.renderActiveBuilds(state, server, { ...config, showCancel: detailed && config.showCancel }, hass)
        : nothing}
    </div>`;
  }

  private renderTileMenu(
    state: BuildTypeState,
    server: ServerInfo,
    config: ResolvedConfig,
    hass: HomeAssistant,
  ): TemplateResult {
    const deviceId = state.info.device_id;
    const items: TemplateResult[] = [];
    if (config.showPause && deviceId) {
      const pause = !state.paused;
      items.push(html`<button
        class="menu-item"
        @click=${() => {
          this._menuOpen = false;
          const key = `pause:${state.info.id}`;
          const action = () => setPaused(hass, deviceId, pause);
          if (pause) {
            this.confirm(`Pause ${state.info.name}? New builds won't start until it is unpaused.`, "Pause", key, action);
          } else {
            void this.perform(key, action);
          }
        }}
      >
        <ha-icon .icon=${pause ? "mdi:pause" : "mdi:play-pause"}></ha-icon>${pause ? "Pause" : "Unpause"}
      </button>`);
    }
    if (config.showCancel) {
      const active = [
        ...state.running.map((build) => ({
          id: build.build_id,
          label: `running build ${buildLabel(build.build_number, build.build_id)}`,
        })),
        ...state.queuedBuildIds.map((id) => ({ id, label: `queued build ${String(id)}` })),
      ];
      for (const build of active) {
        items.push(html`<button
          class="menu-item"
          @click=${() => {
            this._menuOpen = false;
            this.confirm(`Cancel ${build.label} of ${state.info.name}?`, "Cancel build", `cancel:${String(build.id)}`, () =>
              cancelBuild(hass, server.entry_id, build.id),
            );
          }}
        >
          <ha-icon icon="mdi:stop"></ha-icon>Cancel ${build.label}
        </button>`);
      }
    }
    return html`<div class="menu" role="menu">
      ${items.length ? items : html`<div class="muted menu-empty">Nothing to do</div>`}
    </div>`;
  }

  private renderConfirmation(confirmation: PendingConfirmation): TemplateResult {
    return html`<div class="overlay">
      <div class="dialog" role="alertdialog" aria-modal="true" aria-label="Confirm">
        <p>${confirmation.message}</p>
        <div class="dialog-actions">
          <button
            class="icon-button"
            @click=${() => {
              this._confirmation = undefined;
            }}
          >
            Keep
          </button>
          <button
            class="icon-button danger confirm"
            @click=${() => {
              this._confirmation = undefined;
              void confirmation.action();
            }}
          >
            ${confirmation.confirmLabel}
          </button>
        </div>
      </div>
    </div>`;
  }

  private toggleExpanded(buildTypeId: string): void {
    const expanded = new Set(this._expanded);
    if (!expanded.delete(buildTypeId)) {
      expanded.add(buildTypeId);
    }
    this._expanded = expanded;
  }

  private confirm(
    message: string,
    confirmLabel: string,
    key: string,
    action: () => Promise<void>,
  ): void {
    this._confirmation = {
      message,
      confirmLabel,
      action: () => this.perform(key, action),
    };
  }

  private async perform(key: string, action: () => Promise<void>): Promise<void> {
    this._busy = new Set([...this._busy, key]);
    try {
      await action();
      this._actionError = undefined;
    } catch (error) {
      this._actionError = errorMessage(error);
    } finally {
      const busy = new Set(this._busy);
      busy.delete(key);
      this._busy = busy;
    }
  }

  static override styles = [
    sharedStyles,
    css`
      ha-card {
        position: relative;
        padding: 12px 16px;
        overflow: hidden;
      }
      .header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: var(--tc-gap);
        margin-bottom: 4px;
      }
      .title {
        font-size: 1.25em;
        font-weight: 500;
      }
      .summary {
        display: flex;
        gap: 12px;
        flex: none;
      }
      .group-name {
        margin: 12px 0 2px;
        font-weight: 500;
        color: var(--tc-muted);
      }
      .row {
        border-bottom: 1px solid var(--tc-border);
        padding: 4px 0;
      }
      .row:last-child {
        border-bottom: none;
      }
      .unavailable {
        opacity: 0.5;
      }
      .row-main {
        display: flex;
        align-items: center;
        gap: var(--tc-gap);
        min-height: 40px;
      }
      .names {
        display: flex;
        flex-direction: column;
        flex: 1;
        min-width: 0;
      }
      .name {
        font-weight: 500;
      }
      .actions {
        display: flex;
        flex: none;
      }
      .badge {
        flex: none;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        background: var(--warning-color, #ffa600);
        color: var(--text-primary-color, #fff);
      }
      .active {
        display: flex;
        flex-direction: column;
        gap: 4px;
        padding: 0 0 4px 30px;
      }
      .running {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-areas: "label cancel" "bar cancel";
        column-gap: var(--tc-gap);
        align-items: center;
      }
      .progress-label {
        grid-area: label;
        display: flex;
        justify-content: space-between;
        gap: var(--tc-gap);
        min-width: 0;
      }
      .progress {
        grid-area: bar;
        height: 6px;
        border-radius: 3px;
        background: var(--tc-border);
        overflow: hidden;
      }
      .progress-fill {
        height: 100%;
        background: var(--info-color, #039be5);
        transition: width 0.5s ease;
      }
      .running .icon-button {
        grid-area: cancel;
      }
      .queued {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px;
      }
      .tile-detail {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 4px 0 4px 30px;
        min-width: 0;
      }
      .menu {
        display: flex;
        flex-direction: column;
        margin: 4px 0;
        border: 1px solid var(--tc-border);
        border-radius: 8px;
        padding: 4px;
      }
      .menu-item {
        display: flex;
        align-items: center;
        gap: var(--tc-gap);
        border: none;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        padding: 8px;
        border-radius: 6px;
        cursor: pointer;
        --mdc-icon-size: 20px;
      }
      .menu-item:hover {
        background: var(--secondary-background-color, rgba(127, 127, 127, 0.15));
      }
      .menu-empty {
        padding: 8px;
      }
      .section {
        margin-top: 8px;
      }
      .message {
        padding: 8px 0;
      }
      .banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--tc-gap);
        margin-top: 8px;
      }
      .overlay {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        background: rgba(0, 0, 0, 0.4);
      }
      .dialog {
        max-width: 360px;
        width: 100%;
        padding: 16px;
        border-radius: var(--ha-card-border-radius, 12px);
        background: var(--card-background-color, var(--primary-background-color));
        color: var(--primary-text-color);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
      }
      .dialog p {
        margin: 0 0 12px;
        overflow-wrap: anywhere;
      }
      .dialog-actions {
        display: flex;
        justify-content: flex-end;
        gap: var(--tc-gap);
      }
      @media (max-width: 500px) {
        .active,
        .tile-detail {
          padding-left: 0;
        }
      }
    `,
  ];
}

/** Changes whenever a build starts, finishes or is queued, so detail views refetch. */
function refreshKey(state: BuildTypeState): string {
  return [
    state.lastBuildNumber,
    state.lastFinished,
    ...state.running.map((build) => build.build_id),
    ...state.queuedBuildIds,
  ].join("|");
}


declare global {
  interface HTMLElementTagNameMap {
    "teamcity-card": TeamCityCard;
  }
}
