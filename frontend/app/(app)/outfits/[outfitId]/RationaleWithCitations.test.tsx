import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RationaleWithCitations } from "./RationaleWithCitations";

describe("RationaleWithCitations", () => {
  it("renders [n] tokens as citation badges inline", () => {
    render(
      <RationaleWithCitations
        rationaleText="A clean, casual pairing."
        rationaleWithCitations="A clean, casual pairing. [1]"
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(/A clean, casual pairing\./)).toBeInTheDocument();
    // The raw token itself must not leak through as literal text.
    expect(screen.queryByText(/\[1]/)).not.toBeInTheDocument();
  });

  it("falls back to plain rationale_text with no badges when rationale_with_citations is empty", () => {
    render(<RationaleWithCitations rationaleText="A cohesive, weather-ready look." rationaleWithCitations="" />);
    expect(screen.getByText("A cohesive, weather-ready look.")).toBeInTheDocument();
  });

  it("handles multiple citation numbers in one string", () => {
    render(
      <RationaleWithCitations
        rationaleText="ignored"
        rationaleWithCitations="First part. [1] Second part. [2][3]"
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
