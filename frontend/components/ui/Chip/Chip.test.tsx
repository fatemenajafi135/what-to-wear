import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("renders inactive by default", () => {
    render(<Chip>Tops</Chip>);
    expect(screen.getByRole("button", { name: "Tops" })).toHaveAttribute("aria-pressed", "false");
  });

  it("renders active state", () => {
    render(<Chip active>Tops</Chip>);
    expect(screen.getByRole("button", { name: "Tops" })).toHaveAttribute("aria-pressed", "true");
  });

  it("calls onClick when pressed", async () => {
    const onClick = vi.fn();
    render(<Chip onClick={onClick}>Tops</Chip>);
    await userEvent.click(screen.getByRole("button", { name: "Tops" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("is disabled and non-interactive when disabled", () => {
    const onClick = vi.fn();
    render(
      <Chip disabled onClick={onClick}>
        Tops
      </Chip>,
    );
    expect(screen.getByRole("button", { name: "Tops" })).toBeDisabled();
  });
});
