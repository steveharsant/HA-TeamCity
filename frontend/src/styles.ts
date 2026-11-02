import { css } from "lit";

export const sharedStyles = css`
  :host {
    --tc-gap: 8px;
    --tc-muted: var(--secondary-text-color);
    --tc-border: var(--divider-color, rgba(127, 127, 127, 0.25));
  }
  a {
    color: inherit;
    text-decoration: none;
  }
  a:hover {
    text-decoration: underline;
  }
  .muted {
    color: var(--tc-muted);
    font-size: 0.875em;
  }
  .status-icon {
    --mdc-icon-size: 22px;
    flex: none;
  }
  .icon-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    border: none;
    border-radius: 18px;
    min-width: 36px;
    height: 36px;
    padding: 0 8px;
    background: transparent;
    color: var(--primary-text-color);
    cursor: pointer;
    font: inherit;
    --mdc-icon-size: 20px;
  }
  .icon-button:hover:not([disabled]) {
    background: var(--secondary-background-color, rgba(127, 127, 127, 0.15));
  }
  .icon-button:focus-visible {
    outline: 2px solid var(--primary-color);
  }
  .icon-button[disabled] {
    color: var(--disabled-text-color);
    cursor: default;
  }
  .icon-button.primary {
    color: var(--primary-color);
  }
  .icon-button.danger {
    color: var(--error-color, #db4437);
  }
  .error {
    color: var(--error-color, #db4437);
    font-size: 0.875em;
    overflow-wrap: anywhere;
  }
  .ellipsis {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  h3 {
    margin: 12px 0 4px;
    font-size: 0.875em;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--tc-muted);
  }
`;
