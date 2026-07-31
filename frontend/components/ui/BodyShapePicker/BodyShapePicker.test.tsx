import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BodyShapePicker } from "./BodyShapePicker";

describe("BodyShapePicker", () => {
  it("renders all five options", () => {
    render(<BodyShapePicker value={null} onChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Hourglass" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pear" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Rectangle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apple" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inverted triangle" })).toBeInTheDocument();
  });

  it("marks only the selected option as pressed", () => {
    render(<BodyShapePicker value="pear" onChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Pear" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Hourglass" })).toHaveAttribute("aria-pressed", "false");
  });

  it("is keyboard operable — Tab reaches an option and Enter selects it", async () => {
    const onChange = vi.fn();
    render(<BodyShapePicker value={null} onChange={onChange} />);

    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Hourglass" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");

    expect(onChange).toHaveBeenCalledWith("hourglass");
  });

  it("calls onChange with the clicked shape", async () => {
    const onChange = vi.fn();
    render(<BodyShapePicker value={null} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "Apple" }));

    expect(onChange).toHaveBeenCalledWith("apple");
  });
});
