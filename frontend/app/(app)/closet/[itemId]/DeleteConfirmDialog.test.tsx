import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DeleteConfirmDialog } from "./DeleteConfirmDialog";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("DeleteConfirmDialog", () => {
  it("renders the item name in the title, the body copy, and both actions", () => {
    render(<DeleteConfirmDialog open itemName="Navy blazer" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Delete Navy blazer?" })).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls onConfirm when Delete is clicked", async () => {
    const onConfirm = vi.fn();
    render(<DeleteConfirmDialog open itemName="Navy blazer" onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  // Confirming sets open=false, which closes the dialog, which dispatches
  // the same `close` event Escape does — so the dismissal callback used to
  // fire on a successful delete too. Harmless here, severe in
  // BulkChoiceSheet, whose dismissal callback navigates. Fixed for all five
  // dialogs at once in lib/useModalDialog.ts.
  it("does not also call onCancel when a confirmed delete closes it", async () => {
    const onCancel = vi.fn();
    const { rerender } = render(
      <DeleteConfirmDialog open itemName="Navy blazer" onConfirm={vi.fn()} onCancel={onCancel} />
    );

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    rerender(<DeleteConfirmDialog open={false} itemName="Navy blazer" onConfirm={vi.fn()} onCancel={onCancel} />);

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("calls onCancel when Cancel is clicked, without confirming", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<DeleteConfirmDialog open itemName="Navy blazer" onConfirm={onConfirm} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("opens the dialog (showModal) when open becomes true", () => {
    const { rerender } = render(
      <DeleteConfirmDialog open={false} itemName="Navy blazer" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled();
    rerender(<DeleteConfirmDialog open itemName="Navy blazer" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
  });
});
