import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import { errorMessage, fetchBuildChanges, fetchBuildHistory, fetchBuildLog } from "./api";
import { buildLabel, duration, relativeTime } from "./format";
import { statusIcon } from "./status";
import { sharedStyles } from "./styles";
import type { Build, Change, ConsoleSection, HomeAssistant } from "./types";

type Loadable<T> =
  | { state: "loading" }
  | { state: "loaded"; value: T }
  | { state: "error"; message: string };

/** Console detail for one build configuration: history, then changes and log of the selected build. */
export class TeamCityBuildDetail extends LitElement {
  static override properties = {
    hass: { attribute: false },
    entryId: { attribute: false },
    buildTypeId: { attribute: false },
    sections: { attribute: false },
    historyCount: { attribute: false },
    logLines: { attribute: false },
    canViewLogs: { attribute: false },
    refreshKey: { attribute: false },
    _history: { state: true },
    _selectedBuildId: { state: true },
    _changes: { state: true },
    _log: { state: true },
  };

  declare hass: HomeAssistant;
  declare entryId: string;
  declare buildTypeId: string;
  declare sections: ConsoleSection[];
  declare historyCount: number;
  declare logLines: number;
  declare canViewLogs: boolean;
  declare refreshKey: string;
  declare private _history: Loadable<Build[]> | undefined;
  declare private _selectedBuildId: number | undefined;
  declare private _changes: Loadable<Change[]> | undefined;
  declare private _log: Loadable<string[]> | undefined;

  private get showLog(): boolean {
    return this.sections.includes("log") && this.canViewLogs;
  }

  protected override updated(changed: PropertyValues<this>): void {
    if ((changed as Map<PropertyKey, unknown>).has("_log")) {
      const log = this.renderRoot.querySelector(".log");
      if (log) {
        log.scrollTop = log.scrollHeight;
      }
    }
    if (
      changed.has("entryId") ||
      changed.has("buildTypeId") ||
      changed.has("refreshKey") ||
      changed.has("historyCount")
    ) {
      void this.loadHistory();
    }
  }

  private async loadHistory(): Promise<void> {
    const showHistory = this.sections.includes("history");
    if (!showHistory && !this.sections.includes("changes") && !this.showLog) {
      return;
    }
    this._history ??= { state: "loading" };
    try {
      const builds = await fetchBuildHistory(
        this.hass,
        this.entryId,
        this.buildTypeId,
        showHistory ? this.historyCount : 1,
      );
      this._history = { state: "loaded", value: builds };
      const stillListed = builds.some((build) => build.id === this._selectedBuildId);
      const selected = stillListed ? this._selectedBuildId : builds[0]?.id;
      if (selected !== undefined) {
        void this.selectBuild(selected);
      }
    } catch (error) {
      this._history = { state: "error", message: errorMessage(error) };
    }
  }

  private async selectBuild(buildId: number): Promise<void> {
    this._selectedBuildId = buildId;
    const tasks: Promise<void>[] = [];
    if (this.sections.includes("changes")) {
      this._changes = { state: "loading" };
      tasks.push(
        fetchBuildChanges(this.hass, this.entryId, buildId).then(
          (value) => {
            if (this._selectedBuildId === buildId) this._changes = { state: "loaded", value };
          },
          (error: unknown) => {
            if (this._selectedBuildId === buildId)
              this._changes = { state: "error", message: errorMessage(error) };
          },
        ),
      );
    }
    if (this.showLog) {
      this._log = { state: "loading" };
      tasks.push(
        fetchBuildLog(this.hass, this.entryId, buildId, this.logLines).then(
          (value) => {
            if (this._selectedBuildId === buildId) this._log = { state: "loaded", value };
          },
          (error: unknown) => {
            if (this._selectedBuildId === buildId)
              this._log = { state: "error", message: errorMessage(error) };
          },
        ),
      );
    }
    await Promise.all(tasks);
  }

  protected override render(): TemplateResult {
    const language = this.hass.locale?.language ?? this.hass.language;
    return html`
      ${this.sections.includes("history")
        ? html`<h3>Recent builds</h3>
            ${renderLoadable(this._history, (builds) =>
              builds.length
                ? html`<div class="history" role="list">
                    ${builds.map((build) => this.renderHistoryRow(build, language))}
                  </div>`
                : html`<div class="muted">No builds yet</div>`,
            )}`
        : nothing}
      ${this.sections.includes("changes") && this._selectedBuildId !== undefined
        ? html`<h3>Changes in ${this.selectedLabel()}</h3>
            ${renderLoadable(this._changes, (changes) =>
              changes.length
                ? html`<ul class="changes">
                    ${changes.map((change) => renderChange(change, language))}
                  </ul>`
                : html`<div class="muted">No changes</div>`,
            )}`
        : nothing}
      ${this.showLog && this._selectedBuildId !== undefined
        ? html`<h3>Log of ${this.selectedLabel()} (last ${String(this.logLines)} lines)</h3>
            ${renderLoadable(this._log, (lines) =>
              html`<pre class="log">${lines.join("\n")}</pre>`,
            )}`
        : nothing}
    `;
  }

  private selectedLabel(): string {
    const history = this._history?.state === "loaded" ? this._history.value : [];
    const build = history.find((item) => item.id === this._selectedBuildId);
    return build ? buildLabel(build.number, build.id) : "build";
  }

  private renderHistoryRow(build: Build, language: string): TemplateResult {
    const selected = build.id === this._selectedBuildId;
    const status = build.state === "running" ? "running" : build.status;
    const took = duration(build.start_date, build.finish_date);
    return html`<div class="history-row ${selected ? "selected" : ""}" role="listitem">
      <button
        class="select"
        aria-pressed=${selected ? "true" : "false"}
        @click=${() => void this.selectBuild(build.id)}
      >
        ${statusIcon(status)}
        <span class="number">${buildLabel(build.number, build.id)}</span>
        <span class="ellipsis branch">${build.branch_name ?? ""}</span>
        <span class="ellipsis muted trigger">${build.triggered_by ?? ""}</span>
        <span class="muted when">
          ${build.finish_date
            ? relativeTime(build.finish_date, language)
            : build.state === "running"
              ? `${String(build.percentage_complete ?? 0)}%`
              : ""}
          ${took ? html` · ${took}` : nothing}
        </span>
      </button>
      ${build.web_url
        ? html`<a
            class="icon-button"
            href=${build.web_url}
            target="_blank"
            rel="noreferrer"
            title="Open in TeamCity"
            ><ha-icon icon="mdi:open-in-new"></ha-icon
          ></a>`
        : nothing}
    </div>`;
  }

  static override styles = [
    sharedStyles,
    css`
      :host {
        display: block;
        padding: 0 0 8px 30px;
      }
      .history {
        display: flex;
        flex-direction: column;
      }
      .history-row {
        display: flex;
        align-items: center;
        border-radius: 6px;
      }
      .select {
        flex: 1;
        min-width: 0;
        display: grid;
        grid-template-columns: 22px 4.5em minmax(0, 1fr) minmax(0, 0.8fr) auto;
        align-items: center;
        gap: var(--tc-gap);
        border: none;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        padding: 2px 4px;
        border-radius: 6px;
        cursor: pointer;
      }
      .select:focus-visible {
        outline: 2px solid var(--primary-color);
      }
      .history-row:hover {
        background: var(--secondary-background-color, rgba(127, 127, 127, 0.15));
      }
      .history-row.selected {
        background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.12);
      }
      .when {
        white-space: nowrap;
      }
      .changes {
        list-style: none;
        padding: 0;
        margin: 0;
      }
      .changes li {
        padding: 2px 0;
        overflow-wrap: anywhere;
      }
      .log {
        max-height: 320px;
        overflow: auto;
        margin: 0;
        padding: 8px;
        border-radius: 6px;
        background: var(--code-editor-background-color, rgba(127, 127, 127, 0.1));
        font-size: 0.8em;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      @media (max-width: 500px) {
        :host {
          padding-left: 0;
        }
        .select {
          grid-template-columns: 22px 4.5em minmax(0, 1fr) auto;
        }
        .trigger {
          display: none;
        }
      }
    `,
  ];
}

function renderLoadable<T>(
  value: Loadable<T> | undefined,
  render: (value: T) => TemplateResult,
): TemplateResult {
  if (!value || value.state === "loading") {
    return html`<div class="muted">Loading…</div>`;
  }
  if (value.state === "error") {
    return html`<div class="error">${value.message}</div>`;
  }
  return render(value.value);
}

function renderChange(change: Change, language: string): TemplateResult {
  const summary = change.comment?.split("\n", 1)[0] ?? "";
  return html`<li>
    <span>${summary}</span>
    <span class="muted">
      — ${change.username ?? "unknown"}${change.version
        ? html` · <code>${change.version.slice(0, 8)}</code>`
        : nothing}${change.date ? html` · ${relativeTime(change.date, language)}` : nothing}
    </span>
  </li>`;
}


declare global {
  interface HTMLElementTagNameMap {
    "teamcity-build-detail": TeamCityBuildDetail;
  }
}
