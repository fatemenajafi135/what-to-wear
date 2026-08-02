import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MatchBreakdown } from "./MatchBreakdown";

describe("MatchBreakdown", () => {
  it("renders the match level label and one bar per dimension", () => {
    render(
      <MatchBreakdown
        matchLabel="great"
        dimensionScores={[
          { dimension: "color_harmony", value: 0.82 },
          { dimension: "formality_coherence", value: 0.6 },
          { dimension: "weather_fitness", value: 0.4 },
          { dimension: "silhouette_balance", value: 0.9 },
        ]}
      />,
    );
    expect(screen.getByText("Great match")).toBeInTheDocument();
    expect(screen.getByText("Color harmony")).toBeInTheDocument();
    expect(screen.getByText("Formality")).toBeInTheDocument();
    expect(screen.getByText("Weather fit")).toBeInTheDocument();
    expect(screen.getByText("Silhouette")).toBeInTheDocument();
  });

  it("never renders a numeric score or percentage anywhere in its output", () => {
    const { container } = render(
      <MatchBreakdown
        matchLabel="good"
        dimensionScores={[
          { dimension: "color_harmony", value: 0.8231 },
          { dimension: "formality_coherence", value: 0.6 },
        ]}
      />,
    );
    // Constitution II / FR-004 / SC-003: the float must only ever drive a
    // CSS width, never appear as visible text — this is the direct guard
    // for the surface most likely to leak one.
    expect(container.textContent).not.toMatch(/0\.\d/);
    expect(container.textContent).not.toMatch(/\d+%/);
    expect(container.textContent).not.toMatch(/\b\d+\b/);
  });

  it("sets each bar's fill width from the dimension's value", () => {
    const { container } = render(
      <MatchBreakdown matchLabel="great" dimensionScores={[{ dimension: "color_harmony", value: 0.75 }]} />,
    );
    const fill = container.querySelector("[style]");
    expect(fill).toHaveStyle({ width: "75%" });
  });

  it("renders nothing extra when dimensionScores is empty (the degrade path)", () => {
    render(<MatchBreakdown matchLabel="might_work" dimensionScores={[]} />);
    expect(screen.getByText("Might work")).toBeInTheDocument();
  });
});
