import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Textarea } from "./Textarea";

describe("Textarea", () => {
  it("associates the label and calls onChange as the user types", async () => {
    const onChange = vi.fn();
    render(<Textarea label="Notes" value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("Notes"), "a");
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("shows an error message and marks the field aria-invalid", () => {
    render(<Textarea label="Notes" value="" onChange={() => {}} error="This field is required." />);
    expect(screen.getByLabelText("Notes")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });

  it("is disabled when the disabled prop is set", () => {
    render(<Textarea label="Notes" value="" onChange={() => {}} disabled />);
    expect(screen.getByLabelText("Notes")).toBeDisabled();
  });
});
