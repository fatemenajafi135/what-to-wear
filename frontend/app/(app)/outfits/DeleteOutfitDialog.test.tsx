import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeleteOutfitDialog } from "./DeleteOutfitDialog";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("DeleteOutfitDialog", () => {
  it("renders the outfit title in the heading, the body copy, and both actions", () => {
    render(<DeleteOutfitDialog open outfitTitle="Rainy day commute" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Delete Rainy day commute?" })).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls onConfirm when Delete is clicked", async () => {
    const onConfirm = vi.fn();
    render(<DeleteOutfitDialog open outfitTitle="Rainy day commute" onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Cancel is clicked, without confirming", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<DeleteOutfitDialog open outfitTitle="Rainy day commute" onConfirm={onConfirm} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("opens the dialog (showModal) when open becomes true", () => {
    const { rerender } = render(
      <DeleteOutfitDialog open={false} outfitTitle="Rainy day commute" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled();
    rerender(<DeleteOutfitDialog open outfitTitle="Rainy day commute" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
  });
});
