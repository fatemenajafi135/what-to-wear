import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DatePicker } from "./DatePicker";

describe("DatePicker", () => {
  it("renders a native date input associated with its label", () => {
    render(<DatePicker label="Birth date" value="1990-01-01" onChange={() => {}} />);
    const input = screen.getByLabelText("Birth date");
    expect(input).toHaveAttribute("type", "date");
    expect(input).toHaveValue("1990-01-01");
  });

  it("shows a toLocaleDateString long-form display alongside the native input", () => {
    render(<DatePicker label="Birth date" value="1990-01-01" onChange={() => {}} />);
    const expected = new Date("1990-01-01T00:00:00").toLocaleDateString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it("calls onChange when a new date is entered", () => {
    const onChange = vi.fn();
    render(<DatePicker label="Birth date" value="1990-01-01" onChange={onChange} />);
    const input = screen.getByLabelText("Birth date");
    fireEvent.change(input, { target: { value: "1991-02-02" } });
    expect(onChange).toHaveBeenCalledWith("1991-02-02");
  });
});
