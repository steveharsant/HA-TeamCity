import { html, type TemplateResult } from "lit";

interface StatusLook {
  icon: string;
  color: string;
  label: string;
}

const LOOKS: Record<string, StatusLook> = {
  success: { icon: "mdi:check-circle", color: "var(--success-color, #43a047)", label: "Success" },
  failure: { icon: "mdi:close-circle", color: "var(--error-color, #db4437)", label: "Failure" },
  running: { icon: "mdi:progress-clock", color: "var(--info-color, #039be5)", label: "Running" },
  paused: { icon: "mdi:pause-circle", color: "var(--warning-color, #ffa600)", label: "Paused" },
  unknown: { icon: "mdi:help-circle", color: "var(--disabled-text-color, #9e9e9e)", label: "Unknown" },
};

const UNKNOWN_LOOK: StatusLook = {
  icon: "mdi:help-circle",
  color: "var(--disabled-text-color, #9e9e9e)",
  label: "Unknown",
};

export function statusLook(status: string | null | undefined): StatusLook {
  return (status && LOOKS[status.toLowerCase()]) || UNKNOWN_LOOK;
}

export function statusIcon(status: string | null | undefined): TemplateResult {
  const look = statusLook(status);
  return html`<ha-icon
    class="status-icon"
    .icon=${look.icon}
    style="color: ${look.color}"
    title=${look.label}
  ></ha-icon>`;
}
