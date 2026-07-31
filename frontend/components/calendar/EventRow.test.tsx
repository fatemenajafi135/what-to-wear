import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EventRow } from "./EventRow";

describe("EventRow", () => {
  it("renders the computed label, not a hardcoded date string", () => {
    render(
      <EventRow
        title="Dinner with Sam"
        start={new Date(Date.now() + 60_000).toISOString()}
        location="Tanto"
        disabled={false}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("Dinner with Sam")).toBeInTheDocument();
    expect(screen.queryByText("Today, 7:30 PM")).not.toBeInTheDocument();
    expect(screen.getByText(/Tanto/)).toBeInTheDocument();
  });

  it("omits the location segment cleanly when location is absent", () => {
    const start = new Date(Date.now() + 60_000).toISOString();
    render(<EventRow title="Focus block" start={start} location={null} disabled={false} onSelect={vi.fn()} />);
    const meta = screen.getByText(/^(Today|Tomorrow)/);
    expect(meta.textContent).not.toContain("·");
  });

  it("calls onSelect when clicked", async () => {
    const onSelect = vi.fn();
    render(
      <EventRow
        title="Dinner"
        start={new Date(Date.now() + 60_000).toISOString()}
        location={null}
        disabled={false}
        onSelect={onSelect}
      />,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("renders disabled with a non-interactive appearance when picked", () => {
    render(
      <EventRow
        title="Dinner"
        start={new Date(Date.now() + 60_000).toISOString()}
        location={null}
        disabled
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
