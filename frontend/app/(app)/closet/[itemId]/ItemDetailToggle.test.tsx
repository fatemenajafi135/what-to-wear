import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ItemDetailToggle } from "./ItemDetailToggle";

describe("ItemDetailToggle", () => {
  it("shows both options with the current value selected", () => {
    render(<ItemDetailToggle value="isolated" onChange={vi.fn()} />);

    expect(screen.getByRole("tab", { name: "Isolated" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Original" })).toHaveAttribute("aria-selected", "false");
  });

  it("calls onChange with the newly picked view", async () => {
    const onChange = vi.fn();
    render(<ItemDetailToggle value="isolated" onChange={onChange} />);

    await userEvent.click(screen.getByRole("tab", { name: "Original" }));

    expect(onChange).toHaveBeenCalledWith("original");
  });
});
