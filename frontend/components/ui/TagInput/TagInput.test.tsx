import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "./TagInput";

describe("TagInput", () => {
  it("renders committed values as list items with a remove button", () => {
    render(<TagInput label="Brands to avoid" values={["Acme", "Zed"]} onChange={() => {}} />);
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Remove Acme" })).toBeInTheDocument();
  });

  it("commits the current text as a new chip on Enter", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Brands to avoid" values={[]} onChange={onChange} />);
    const input = screen.getByLabelText("Brands to avoid");
    await userEvent.type(input, "Acme{Enter}");
    expect(onChange).toHaveBeenCalledWith(["Acme"]);
  });

  it("removes the last chip on Backspace when the field is empty", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Brands to avoid" values={["Acme"]} onChange={onChange} />);
    const input = screen.getByLabelText("Brands to avoid");
    input.focus();
    await userEvent.keyboard("{Backspace}");
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("calls the remove button for a specific chip", async () => {
    const onChange = vi.fn();
    render(<TagInput label="Brands to avoid" values={["Acme", "Zed"]} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove Acme" }));
    expect(onChange).toHaveBeenCalledWith(["Zed"]);
  });
});
