import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnectedAccountsSection } from "./ConnectedAccountsSection";

/**
 * This row is the Settings half of the "two entry points, one state"
 * requirement (docs/handoffs/012-calendar.md §6.4) — it must read and write
 * through `useCalendarConnection`, never its own fetch. Mocking the hook is
 * what lets all three of its states be asserted; the row shipped inert in
 * feature 013 because 012's hook had not merged yet.
 */
const connect = vi.fn();
const disconnect = vi.fn();
const refresh = vi.fn();
let state = { connected: false, connectedAt: null as string | null, isLoading: false, connect, disconnect, refresh };

vi.mock("@/lib/calendar/useCalendarConnection", () => ({
  useCalendarConnection: () => state,
}));

beforeEach(() => {
  vi.clearAllMocks();
  state = { connected: false, connectedAt: null, isLoading: false, connect, disconnect, refresh };
});

describe("ConnectedAccountsSection", () => {
  it("offers Connect when the calendar is not linked", async () => {
    render(<ConnectedAccountsSection />);

    const button = screen.getByRole("button", { name: "Connect" });
    expect(button).toBeEnabled();

    await userEvent.click(button);
    expect(connect).toHaveBeenCalledOnce();
  });

  it("shows a Connected badge and offers Disconnect when linked", async () => {
    state = { ...state, connected: true, connectedAt: "2026-07-31T10:00:00Z" };
    render(<ConnectedAccountsSection />);

    expect(screen.getByText("Connected")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(disconnect).toHaveBeenCalledOnce();
  });

  it("fails closed while the connection state is still unknown", async () => {
    state = { ...state, isLoading: true };
    render(<ConnectedAccountsSection />);

    const button = screen.getByRole("button", { name: "Connect" });
    expect(button).toBeDisabled();

    await userEvent.click(button, { pointerEventsCheck: 0 });
    expect(connect).not.toHaveBeenCalled();
  });

  it("renders Weather services with a non-interactive Coming soon badge", () => {
    render(<ConnectedAccountsSection />);

    expect(screen.getByText("Weather services")).toBeInTheDocument();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });

  it("has no Edit/Done control", () => {
    render(<ConnectedAccountsSection />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Done" })).not.toBeInTheDocument();
  });
});
