import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CameraPrimer } from "./CameraPrimer";

beforeEach(() => {
  // jsdom doesn't implement <dialog> modal behavior — stub the two methods
  // BottomSheet/CalendarPrimer's own pattern already relies on.
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
  });
});

describe("CameraPrimer", () => {
  it("renders title, body, and both actions when open", () => {
    render(<CameraPrimer open onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Before you scan" })).toBeInTheDocument();
    expect(screen.getByText(/fill in its details automatically/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not now" })).toBeInTheDocument();
  });

  it("calls onContinue when Continue is clicked", async () => {
    const onContinue = vi.fn();
    render(<CameraPrimer open onContinue={onContinue} onDismiss={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("calls onDismiss when Not now is clicked", async () => {
    const onDismiss = vi.fn();
    render(<CameraPrimer open onContinue={vi.fn()} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("opens the dialog (showModal) when open becomes true", () => {
    const { rerender } = render(<CameraPrimer open={false} onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled();
    rerender(<CameraPrimer open onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
  });
});
