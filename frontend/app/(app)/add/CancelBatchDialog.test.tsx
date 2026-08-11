import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CancelBatchDialog } from "./CancelBatchDialog";

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("CancelBatchDialog", () => {
  it("renders the title, the saved/total count in the body, and both actions", () => {
    render(<CancelBatchDialog open savedCount={2} total={5} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Cancel this batch?" })).toBeInTheDocument();
    expect(
      screen.getByText("2 of 5 items are already saved to your closet. The rest won't be added.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel batch" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep reviewing" })).toBeInTheDocument();
  });

  it("calls onConfirm when Cancel batch is clicked", async () => {
    const onConfirm = vi.fn();
    render(<CancelBatchDialog open savedCount={1} total={3} onConfirm={onConfirm} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel batch" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Keep reviewing is clicked, without confirming", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<CancelBatchDialog open savedCount={1} total={3} onConfirm={onConfirm} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "Keep reviewing" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  // Same fix as DeleteConfirmDialog/DeleteOutfitDialog (lib/useModalDialog.ts):
  // a confirmed close still dispatches the dialog's `close` event, which
  // must not also fire the dismissal callback.
  it("does not also call onCancel when a confirmed cancel closes it", async () => {
    const onCancel = vi.fn();
    const { rerender } = render(
      <CancelBatchDialog open savedCount={1} total={3} onConfirm={vi.fn()} onCancel={onCancel} />
    );

    await userEvent.click(screen.getByRole("button", { name: "Cancel batch" }));
    rerender(<CancelBatchDialog open={false} savedCount={1} total={3} onConfirm={vi.fn()} onCancel={onCancel} />);

    expect(onCancel).not.toHaveBeenCalled();
  });

  it("opens the dialog (showModal) when open becomes true", () => {
    const { rerender } = render(
      <CancelBatchDialog open={false} savedCount={1} total={3} onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled();
    rerender(<CancelBatchDialog open savedCount={1} total={3} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
  });
});
