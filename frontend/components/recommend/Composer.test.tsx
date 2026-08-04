import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Composer } from "./Composer";

describe("Composer", () => {
  beforeEach(() => {
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
  });

  it("submits on Enter and clears the input", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} inFlight={false} />);
    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "business casual{Enter}");
    expect(onSend).toHaveBeenCalledWith("business casual");
    expect(input).toHaveValue("");
  });

  it("submits on send-button click", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} inFlight={false} />);
    await userEvent.type(screen.getByLabelText("Message"), "rainy commute");
    await userEvent.click(screen.getByLabelText("Send"));
    expect(onSend).toHaveBeenCalledWith("rainy commute");
  });

  it("does not submit empty or whitespace-only input", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} inFlight={false} />);
    await userEvent.type(screen.getByLabelText("Message"), "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input and send button while offline", () => {
    Object.defineProperty(window.navigator, "onLine", { value: false, configurable: true });
    render(<Composer onSend={vi.fn()} inFlight={false} />);
    expect(screen.getByLabelText("Message")).toBeDisabled();
    expect(screen.getByLabelText("Send")).toBeDisabled();
  });

  it("disables input and send button while a request is in flight, with a distinct affordance", () => {
    render(<Composer onSend={vi.fn()} inFlight={true} />);
    expect(screen.getByLabelText("Message")).toBeDisabled();
    // design-system.md "Chat input behavior", Intended (production): the send button shows a
    // visible sending affordance (swapped label/icon), not just a disabled arrow.
    expect(screen.getByLabelText("Sending")).toBeDisabled();
    expect(screen.queryByLabelText("Send")).not.toBeInTheDocument();
  });

  it("shows the plain send affordance again once no longer in flight", () => {
    render(<Composer onSend={vi.fn()} inFlight={false} />);
    expect(screen.getByLabelText("Send")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sending")).not.toBeInTheDocument();
  });
});
