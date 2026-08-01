import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { InsufficientClosetGate } from "./InsufficientClosetGate";

describe("InsufficientClosetGate", () => {
  it("renders the count-only fallback phrase when missing is empty", () => {
    render(<InsufficientClosetGate missing={[]} />);
    expect(screen.getByText(/Add a few more items and I'll get started\./)).toBeInTheDocument();
  });

  it("renders a single missing item", () => {
    render(<InsufficientClosetGate missing={["a pair of shoes"]} />);
    expect(screen.getByText(/Add a pair of shoes and I'll get started\./)).toBeInTheDocument();
  });

  it("joins two missing items with 'and', no Oxford comma", () => {
    render(<InsufficientClosetGate missing={["a top", "a pair of shoes"]} />);
    expect(screen.getByText(/Add a top and a pair of shoes and I'll get started\./)).toBeInTheDocument();
  });

  it("renders the CTA linking to /add", () => {
    render(<InsufficientClosetGate missing={[]} />);
    expect(screen.getByText("Add items to your closet")).toHaveAttribute("href", "/add");
  });
});
