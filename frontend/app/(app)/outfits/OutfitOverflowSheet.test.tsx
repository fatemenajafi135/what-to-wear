import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OutfitOverflowSheet } from "./OutfitOverflowSheet";

beforeEach(() => {
  // jsdom doesn't implement <dialog> modal behavior — BottomSheet relies on
  // showModal()/close(), same stub ItemOverflowSheet.test.tsx already uses.
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("OutfitOverflowSheet", () => {
  it("renders the three rows: Log as worn today, Edit title, Delete", () => {
    render(
      <OutfitOverflowSheet
        open
        onClose={vi.fn()}
        isOnline={true}
        onLogWorn={vi.fn()}
        onEditTitle={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Log as worn today")).toBeInTheDocument();
    expect(screen.getByText("Edit title")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
    // No separate Favorite row — the heart is a direct header/card control,
    // never routed through this menu (spec.md FR-007 fix, /speckit-analyze).
    expect(screen.queryByText(/favorite/i)).not.toBeInTheDocument();
  });

  it("closes then fires the action when a row is selected", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onDelete = vi.fn();
    render(
      <OutfitOverflowSheet
        open
        onClose={onClose}
        isOnline={true}
        onLogWorn={vi.fn()}
        onEditTitle={vi.fn()}
        onDelete={onDelete}
      />,
    );

    await user.click(screen.getByText("Delete"));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("disables every row while offline (FR-014 — wear/rename/delete all disable offline)", () => {
    render(
      <OutfitOverflowSheet
        open
        onClose={vi.fn()}
        isOnline={false}
        onLogWorn={vi.fn()}
        onEditTitle={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Log as worn today").closest("button")).toBeDisabled();
    expect(screen.getByText("Edit title").closest("button")).toBeDisabled();
    expect(screen.getByText("Delete").closest("button")).toBeDisabled();
  });
});
