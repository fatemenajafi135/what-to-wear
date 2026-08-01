import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BulkChoiceSheet } from "./BulkChoiceSheet";

beforeEach(() => {
  // jsdom implements neither method. The polyfill must dispatch `close`,
  // because the platform does: `HTMLDialogElement.close()` fires it whether
  // the caller is Escape or application code. A polyfill that only strips
  // the attribute made this component untestable in the one respect that
  // mattered — it hid a bug where closing after a choice was read as a
  // dismissal and navigated the user off /add mid-upload.
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("BulkChoiceSheet", () => {
  it("renders the title, subtitle, and both option rows", () => {
    render(<BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Add to Closet" })).toBeInTheDocument();
    expect(screen.getByText("Choose how you would like to add items.")).toBeInTheDocument();
    expect(screen.getByText("Add bulk items")).toBeInTheDocument();
    expect(screen.getByText("Upload several photos, one item each")).toBeInTheDocument();
  });

  it("calls onChooseSingle when the single-item row is clicked", async () => {
    const onChooseSingle = vi.fn();
    render(<BulkChoiceSheet open onChooseSingle={onChooseSingle} onChooseBulk={vi.fn()} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText("Add one item"));
    expect(onChooseSingle).toHaveBeenCalledTimes(1);
  });

  it("calls onChooseBulk when the bulk row is clicked", async () => {
    const onChooseBulk = vi.fn();
    render(<BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={onChooseBulk} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText("Add bulk items"));
    expect(onChooseBulk).toHaveBeenCalledTimes(1);
  });

  // `onClose` is wired to navigation away from /add, so firing it on a
  // successful choice sent the user to /closet the moment they picked their
  // photos — uploads continued from an unmounted screen, and no review card
  // ever appeared.
  it("does not call onClose when the parent closes it after a choice", async () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={vi.fn()} onClose={onClose} />
    );

    await userEvent.click(screen.getByText("Add bulk items"));
    rerender(<BulkChoiceSheet open={false} onChooseSingle={vi.fn()} onChooseBulk={vi.fn()} onClose={onClose} />);

    expect(onClose).not.toHaveBeenCalled();
  });

  it("still calls onClose when the user dismisses the sheet itself", () => {
    const onClose = vi.fn();
    render(<BulkChoiceSheet open onChooseSingle={vi.fn()} onChooseBulk={vi.fn()} onClose={onClose} />);

    // What Escape does: the dialog closes itself, dispatching `close`
    // without the parent ever setting open=false.
    screen.getByRole("dialog").dispatchEvent(new Event("close"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
