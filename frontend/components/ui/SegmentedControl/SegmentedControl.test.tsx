import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentedControl } from "./SegmentedControl";

const options = [
  { value: "all", label: "All" },
  { value: "favorited", label: "Favorited" },
];

describe("SegmentedControl", () => {
  it("marks the active option with aria-selected", () => {
    render(<SegmentedControl options={options} value="all" onChange={() => {}} />);
    expect(screen.getByRole("tab", { name: "All" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Favorited" })).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange with the selected option's value", async () => {
    const onChange = vi.fn();
    render(<SegmentedControl options={options} value="all" onChange={onChange} />);
    await userEvent.click(screen.getByRole("tab", { name: "Favorited" }));
    expect(onChange).toHaveBeenCalledWith("favorited");
  });

  it("dims and disables all options when the control is disabled", () => {
    render(<SegmentedControl options={options} value="all" onChange={() => {}} disabled />);
    expect(screen.getByRole("tab", { name: "All" })).toBeDisabled();
    expect(screen.getByRole("tab", { name: "Favorited" })).toBeDisabled();
  });
});
