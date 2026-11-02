import { LitElement, css, html, type PropertyValues, type TemplateResult } from "lit";
import { errorMessage, fetchAgents } from "./api";
import { buildLabel } from "./format";
import { sharedStyles } from "./styles";
import type { Agent, HomeAssistant } from "./types";

/** Server-wide build agent list for the console. */
export class TeamCityAgents extends LitElement {
  static override properties = {
    hass: { attribute: false },
    entryId: { attribute: false },
    buildTypeNames: { attribute: false },
    refreshKey: { attribute: false },
    _agents: { state: true },
    _error: { state: true },
  };

  declare hass: HomeAssistant;
  declare entryId: string;
  declare buildTypeNames: Map<string, string>;
  declare refreshKey: string;
  declare private _agents: Agent[] | undefined;
  declare private _error: string | undefined;

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has("entryId") || changed.has("refreshKey")) {
      void this.load();
    }
  }

  private async load(): Promise<void> {
    try {
      this._agents = await fetchAgents(this.hass, this.entryId);
      this._error = undefined;
    } catch (error) {
      this._error = errorMessage(error);
    }
  }

  protected override render(): TemplateResult {
    return html`<h3>Agents</h3>
      ${this._error
        ? html`<div class="error">${this._error}</div>`
        : this._agents === undefined
          ? html`<div class="muted">Loading…</div>`
          : this._agents.length === 0
            ? html`<div class="muted">No authorized agents</div>`
            : html`<ul>
                ${this._agents.map((agent) => this.renderAgent(agent))}
              </ul>`}`;
  }

  private renderAgent(agent: Agent): TemplateResult {
    const [icon, color, label] = !agent.connected
      ? ["mdi:lan-disconnect", "var(--disabled-text-color)", "Disconnected"]
      : !agent.enabled
        ? ["mdi:cancel", "var(--warning-color, #ffa600)", "Disabled"]
        : agent.running_build
          ? ["mdi:cog-play", "var(--info-color, #039be5)", "Building"]
          : ["mdi:check-circle-outline", "var(--success-color, #43a047)", "Idle"];
    const build = agent.running_build;
    return html`<li>
      <ha-icon .icon=${icon} style="color: ${color}" title=${label}></ha-icon>
      <span class="ellipsis">${agent.name}</span>
      <span class="ellipsis muted">
        ${build
          ? html`${this.buildTypeNames.get(build.build_type_id) ?? build.build_type_id}
            ${build.web_url
              ? html`<a href=${build.web_url} target="_blank" rel="noreferrer"
                  >${buildLabel(build.number, build.id)}</a
                >`
              : buildLabel(build.number, build.id)}`
          : label}
      </span>
    </li>`;
  }

  static override styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      ul {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      li {
        display: grid;
        grid-template-columns: 24px minmax(0, 1fr) minmax(0, 1.5fr);
        gap: var(--tc-gap);
        align-items: center;
        padding: 2px 0;
        --mdc-icon-size: 20px;
      }
    `,
  ];
}


declare global {
  interface HTMLElementTagNameMap {
    "teamcity-agents": TeamCityAgents;
  }
}
