import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CloseAddOverlay } from "./CloseAddOverlay";

const back = vi.fn();
const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back, push }),
}));

beforeEach(() => {
  back.mockReset();
  push.mockReset();
  // jsdom's own default is 1 (a fresh, empty history stack), which isn't
  // representative of /add's real entry point (always reached via in-app
  // navigation, per docs/design-decisions.md §9) — set >1 by default so
  // these tests exercise the back() path most closings actually take, and
  // override to 1 explicitly in the one test for the fallback case.
  Object.defineProperty(window.history, "length", { value: 2, configurable: true });
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  });
});

describe("CloseAddOverlay", () => {
  it("closes immediately with no confirmation prop (the choice sheet, single-item flow)", async () => {
    render(<CloseAddOverlay />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(back).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("heading", { name: "Cancel this batch?" })).not.toBeInTheDocument();
  });

  it("closes immediately when confirmation is null (bulk batch, nothing saved yet)", async () => {
    render(<CloseAddOverlay confirmation={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(back).toHaveBeenCalledTimes(1);
  });

  it("asks for confirmation instead of closing once a bulk batch has a saved item", async () => {
    render(<CloseAddOverlay confirmation={{ savedCount: 2, total: 5 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(back).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Cancel this batch?" })).toBeInTheDocument();
    expect(
      screen.getByText("2 of 5 items are already saved to your closet. The rest won't be added.")
    ).toBeInTheDocument();
  });

  it("Keep reviewing dismisses the dialog without navigating away", async () => {
    render(<CloseAddOverlay confirmation={{ savedCount: 2, total: 5 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep reviewing" }));

    expect(back).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("Cancel batch confirms and then navigates away", async () => {
    render(<CloseAddOverlay confirmation={{ savedCount: 2, total: 5 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel batch" }));

    expect(back).toHaveBeenCalledTimes(1);
  });

  it("falls back to /closet when there's no history to go back to", async () => {
    const originalLength = window.history.length;
    Object.defineProperty(window.history, "length", { value: 1, configurable: true });

    render(<CloseAddOverlay />);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(push).toHaveBeenCalledWith("/closet");

    Object.defineProperty(window.history, "length", { value: originalLength, configurable: true });
  });
});
