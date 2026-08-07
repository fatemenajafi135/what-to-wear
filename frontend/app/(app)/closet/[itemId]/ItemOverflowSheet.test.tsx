import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ItemOverflowSheet } from "./ItemOverflowSheet";

beforeEach(() => {
  // jsdom doesn't implement <dialog> modal behavior — BottomSheet relies on
  // showModal()/close(), same stub CalendarPrimer.test.tsx already uses.
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

function renderSheet(overrides: Partial<React.ComponentProps<typeof ItemOverflowSheet>> = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    isOnline: true,
    onEdit: vi.fn(),
    onLogWorn: vi.fn(),
    onToggleFavorite: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  render(<ItemOverflowSheet {...props} />);
  return props;
}

describe("ItemOverflowSheet", () => {
  it("renders the four rows in design order", () => {
    renderSheet();
    const buttons = screen.getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Edit", "Log as worn today", "Favorite", "Delete"]);
  });

  it("calls onEdit and closes when Edit is selected", async () => {
    const props = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(props.onEdit).toHaveBeenCalledTimes(1);
    expect(props.onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onToggleFavorite when Favorite is selected", async () => {
    const props = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Favorite" }));
    expect(props.onToggleFavorite).toHaveBeenCalledTimes(1);
  });

  it("calls onDelete when Delete is selected", async () => {
    const props = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(props.onDelete).toHaveBeenCalledTimes(1);
  });

  it("disables Log as worn today while offline", () => {
    renderSheet({ isOnline: false });
    expect(screen.getByRole("button", { name: "Log as worn today" })).toBeDisabled();
  });

  it("leaves Log as worn today enabled while online", () => {
    renderSheet({ isOnline: true });
    expect(screen.getByRole("button", { name: "Log as worn today" })).toBeEnabled();
  });

  it("does not call onLogWorn when disabled and clicked", async () => {
    const props = renderSheet({ isOnline: false });
    await userEvent.click(screen.getByRole("button", { name: "Log as worn today" }));
    expect(props.onLogWorn).not.toHaveBeenCalled();
  });
});
