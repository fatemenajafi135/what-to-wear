import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Select } from "./Select";

const options = [
  { value: "xs", label: "XS" },
  { value: "s", label: "S" },
];

describe("Select", () => {
  it("renders a native select associated with its label", () => {
    render(<Select label="Top size" value="xs" onChange={() => {}} options={options} />);
    const select = screen.getByLabelText("Top size");
    expect(select.tagName).toBe("SELECT");
  });

  it("calls onChange with the selected value", async () => {
    const onChange = vi.fn();
    render(<Select label="Top size" value="xs" onChange={onChange} options={options} />);
    await userEvent.selectOptions(screen.getByLabelText("Top size"), "s");
    expect(onChange).toHaveBeenCalledWith("s");
  });

  it("shows an error message and marks the field aria-invalid", () => {
    render(
      <Select label="Top size" value="xs" onChange={() => {}} options={options} error="This field is required." />,
    );
    expect(screen.getByLabelText("Top size")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });
});
