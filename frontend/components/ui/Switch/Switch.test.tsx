import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Switch } from "./Switch";

describe("Switch", () => {
  it("has role=switch and aria-checked reflecting state", () => {
    render(<Switch checked={false} onChange={() => {}} />);
    const el = screen.getByRole("switch");
    expect(el).toHaveAttribute("aria-checked", "false");
  });

  it("toggles on click", async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} />);
    await userEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("toggles on Space and Enter keydown", async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} />);
    const el = screen.getByRole("switch");
    el.focus();
    await userEvent.keyboard(" ");
    expect(onChange).toHaveBeenCalledWith(true);
    await userEvent.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("is not focusable (tabIndex -1) and non-interactive when disabled", () => {
    render(<Switch checked={false} onChange={() => {}} disabled />);
    const el = screen.getByRole("switch");
    expect(el).toHaveAttribute("aria-disabled", "true");
    expect(el).toHaveAttribute("tabIndex", "-1");
    expect(el).toBeDisabled();
  });
});
