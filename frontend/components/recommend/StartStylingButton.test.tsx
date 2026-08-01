import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { StartStylingButton } from "./StartStylingButton";

describe("StartStylingButton", () => {
  beforeEach(() => {
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
  });

  it("renders nothing when not visible", () => {
    render(<StartStylingButton visible={false} hasPending={true} inFlight={false} onClick={vi.fn()} />);
    expect(screen.queryByText("Start styling")).not.toBeInTheDocument();
  });

  it("is enabled when visible with a pending message", () => {
    render(<StartStylingButton visible={true} hasPending={true} inFlight={false} onClick={vi.fn()} />);
    expect(screen.getByText("Start styling")).toBeEnabled();
  });

  it("is disabled with nothing pending", () => {
    render(<StartStylingButton visible={true} hasPending={false} inFlight={false} onClick={vi.fn()} />);
    expect(screen.getByText("Start styling")).toBeDisabled();
  });

  it("is disabled while a request is in flight even with a pending message", () => {
    render(<StartStylingButton visible={true} hasPending={true} inFlight={true} onClick={vi.fn()} />);
    expect(screen.getByText("Start styling")).toBeDisabled();
  });

  it("is disabled while offline even with a pending message", () => {
    Object.defineProperty(window.navigator, "onLine", { value: false, configurable: true });
    render(<StartStylingButton visible={true} hasPending={true} inFlight={false} onClick={vi.fn()} />);
    expect(screen.getByText("Start styling")).toBeDisabled();
  });
});
