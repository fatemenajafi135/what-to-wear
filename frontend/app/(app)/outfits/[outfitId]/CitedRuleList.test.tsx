import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitedRuleList } from "./CitedRuleList";

describe("CitedRuleList", () => {
  it("renders a numbered row per citation", () => {
    render(
      <CitedRuleList
        citations={[
          { number: 1, text: "Pair casual denim with a relaxed top." },
          { number: 2, text: "Layer a cardigan for cooler weather." },
        ]}
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Pair casual denim with a relaxed top.")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Layer a cardigan for cooler weather.")).toBeInTheDocument();
  });

  it("renders nothing when there are no citations", () => {
    const { container } = render(<CitedRuleList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
