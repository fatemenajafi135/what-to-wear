import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CalendarPrimer } from "./CalendarPrimer";

beforeEach(() => {
  // jsdom doesn't implement <dialog> modal behavior — stub the two methods
  // BottomSheet's own pattern already relies on, matching that precedent.
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("CalendarPrimer", () => {
  it("renders title, body, and both actions when open", () => {
    render(<CalendarPrimer open onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Before you connect" })).toBeInTheDocument();
    expect(screen.getByText(/suggest outfits for what's actually on your schedule/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue to Google" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not now" })).toBeInTheDocument();
  });

  it("calls onContinue when Continue to Google is clicked", async () => {
    const onContinue = vi.fn();
    render(<CalendarPrimer open onContinue={onContinue} onDismiss={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Continue to Google" }));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });

  it("calls onDismiss when Not now is clicked", async () => {
    const onDismiss = vi.fn();
    render(<CalendarPrimer open onContinue={vi.fn()} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("opens the dialog (showModal) when open becomes true", () => {
    const { rerender } = render(<CalendarPrimer open={false} onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).not.toHaveBeenCalled();
    rerender(<CalendarPrimer open onContinue={vi.fn()} onDismiss={vi.fn()} />);
    expect(HTMLDialogElement.prototype.showModal).toHaveBeenCalledTimes(1);
  });
});
