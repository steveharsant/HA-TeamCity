import { LitElement, css, html, type PropertyValues, type TemplateResult } from "lit";
import { errorMessage, fetchBuildHistory } from "./api";
import { TILE_HISTORY_COUNT } from "./config";
import { buildLabel } from "./format";
import { statusLook } from "./status";
import type { Build, HomeAssistant } from "./types";

/** The last few builds of a configuration as coloured blocks, oldest first. */
export class TeamCityBuildStrip extends LitElement {
  static override properties = {
    hass: { attribute: false },
    entryId: { attribute: false },
    buildTypeId: { attribute: false },
    refreshKey: { attribute: false },
    _builds: { state: true },
    _error: { state: true },
  };

  declare hass: HomeAssistant;
  declare entryId: string;
  declare buildTypeId: string;
  declare refreshKey: string;
  declare private _builds: Build[] | undefined;
  declare private _error: string | undefined;

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has("entryId") || changed.has("buildTypeId") || changed.has("refreshKey")) {
      void this.load();
    }
  }

  private async load(): Promise<void> {
    try {
      this._builds = await fetchBuildHistory(
        this.hass,
        this.entryId,
        this.buildTypeId,
        TILE_HISTORY_COUNT,
      );
      this._error = undefined;
    } catch (error) {
      this._error = errorMessage(error);
    }
  }

  protected override render(): TemplateResult {
    if (this._error) {
      return html`<span class="error" title=${this._error}>History unavailable</span>`;
    }
    return html`${[...(this._builds ?? [])].reverse().map((build) => {
      const look = statusLook(build.state === "running" ? "running" : build.status);
      const label = `${buildLabel(build.number, build.id)}: ${look.label}`;
      return html`<a
        class="block"
        style="background: ${look.color}"
        href=${build.web_url ?? "#"}
        target="_blank"
        rel="noreferrer"
        title=${label}
        aria-label=${label}
      ></a>`;
    })}`;
  }

  static override styles = css`
    :host {
      display: flex;
      gap: 3px;
      align-items: center;
    }
    .block {
      width: 14px;
      height: 14px;
      border-radius: 3px;
    }
    .error {
      color: var(--error-color, #db4437);
      font-size: 0.8em;
    }
  `;
}


declare global {
  interface HTMLElementTagNameMap {
    "teamcity-build-strip": TeamCityBuildStrip;
  }
}
