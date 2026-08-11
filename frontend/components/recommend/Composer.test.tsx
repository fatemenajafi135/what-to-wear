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

  it("renders with initialValue pre-filled and editable", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} inFlight={false} initialValue="Dinner with Ana, Fri 8:00 PM" />);
    const input = screen.getByLabelText("Message");
    expect(input).toHaveValue("Dinner with Ana, Fri 8:00 PM");

    await userEvent.clear(input);
    await userEvent.type(input, "actually let's do the beach{Enter}");
    expect(onSend).toHaveBeenCalledWith("actually let's do the beach");
  });

  it("sends initialValue as-is when the user submits without editing it", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} inFlight={false} initialValue="Dinner with Ana, Fri 8:00 PM" />);
    await userEvent.click(screen.getByLabelText("Send"));
    expect(onSend).toHaveBeenCalledWith("Dinner with Ana, Fri 8:00 PM");
  });

  it("does not clobber text the user has already typed when initialValue changes", async () => {
    const { rerender } = render(<Composer onSend={vi.fn()} inFlight={false} initialValue="First event" />);
    const input = screen.getByLabelText("Message");
    await userEvent.clear(input);
    await userEvent.type(input, "my own words");

    rerender(<Composer onSend={vi.fn()} inFlight={false} initialValue="A different event" />);
    expect(screen.getByLabelText("Message")).toHaveValue("my own words");
  });

  it("adopts initialValue once it becomes available after mount, while the field is still untouched", () => {
    // Found in manual browser verification (specs/020-calendar-pick-to-recommend, T023):
    // pickedEventStore's hydration is async, so on a fresh page load Composer often mounts
    // BEFORE the picked event is known — initialValue arrives as undefined first, then a real
    // string a render later. Capturing it only via useState's initializer misses this entirely.
    const { rerender } = render(<Composer onSend={vi.fn()} inFlight={false} initialValue={undefined} />);
    expect(screen.getByLabelText("Message")).toHaveValue("");

    rerender(<Composer onSend={vi.fn()} inFlight={false} initialValue="Dinner with Ana, Fri 8:00 PM" />);
    expect(screen.getByLabelText("Message")).toHaveValue("Dinner with Ana, Fri 8:00 PM");
  });

  it("does not adopt a late-arriving initialValue once the user has already typed something", async () => {
    const { rerender } = render(<Composer onSend={vi.fn()} inFlight={false} initialValue={undefined} />);
    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "already typing");

    rerender(<Composer onSend={vi.fn()} inFlight={false} initialValue="Dinner with Ana, Fri 8:00 PM" />);
    expect(screen.getByLabelText("Message")).toHaveValue("already typing");
  });
});
