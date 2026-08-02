import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OutfitCard } from "./OutfitCard";
import type { components } from "@/lib/api/schema";

type StylingOutfit = components["schemas"]["StylingOutfit"];

const OUTFIT: StylingOutfit = {
  id: "outfit-1",
  occasion: "Rainy day commute",
  rationale_text: "A cohesive, weather-ready look built around a warm coat.",
  items: [],
  match_label: "great",
  meta_line: "Rainy day commute · rain",
  favorite: true,
};

describe("OutfitCard", () => {
  it("renders the title, match label, description and meta line with no citation markers", () => {
    render(
      <OutfitCard
        outfit={OUTFIT}
        saved={false}
        feedback={null}
        onToggleHeart={vi.fn()}
        onFeedback={vi.fn()}
        onCardTap={vi.fn()}
      />,
    );
    expect(screen.getByText("Rainy day commute")).toBeInTheDocument();
    expect(screen.getByText("Great match")).toBeInTheDocument();
    expect(screen.getByText(/A cohesive, weather-ready look/)).toBeInTheDocument();
    expect(screen.getByText("Rainy day commute · rain")).toBeInTheDocument();
    expect(screen.queryByText(/\[\d+]/)).not.toBeInTheDocument();
  });

  it("shows an outline heart when unsaved and a filled one when saved", () => {
    const { rerender } = render(
      <OutfitCard
        outfit={OUTFIT}
        saved={false}
        feedback={null}
        onToggleHeart={vi.fn()}
        onFeedback={vi.fn()}
        onCardTap={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Save outfit")).toBeInTheDocument();

    rerender(
      <OutfitCard
        outfit={OUTFIT}
        saved={true}
        feedback={null}
        onToggleHeart={vi.fn()}
        onFeedback={vi.fn()}
        onCardTap={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Unsave outfit")).toBeInTheDocument();
  });

  it("tapping the heart calls onToggleHeart and not onCardTap", async () => {
    const user = userEvent.setup();
    const onToggleHeart = vi.fn();
    const onCardTap = vi.fn();
    render(
      <OutfitCard
        outfit={OUTFIT}
        saved={false}
        feedback={null}
        onToggleHeart={onToggleHeart}
        onFeedback={vi.fn()}
        onCardTap={onCardTap}
      />,
    );

    await user.click(screen.getByLabelText("Save outfit"));

    expect(onToggleHeart).toHaveBeenCalledTimes(1);
    expect(onCardTap).not.toHaveBeenCalled();
  });

  it("tapping the card body (not the heart or thumbnails) calls onCardTap", async () => {
    const user = userEvent.setup();
    const onCardTap = vi.fn();
    render(
      <OutfitCard
        outfit={OUTFIT}
        saved={false}
        feedback={null}
        onToggleHeart={vi.fn()}
        onFeedback={vi.fn()}
        onCardTap={onCardTap}
      />,
    );

    await user.click(screen.getByText("Rainy day commute"));

    expect(onCardTap).toHaveBeenCalledTimes(1);
  });

  it("tapping a feedback thumb calls onFeedback and not onCardTap", async () => {
    const user = userEvent.setup();
    const onFeedback = vi.fn();
    const onCardTap = vi.fn();
    render(
      <OutfitCard
        outfit={OUTFIT}
        saved={false}
        feedback={null}
        onToggleHeart={vi.fn()}
        onFeedback={onFeedback}
        onCardTap={onCardTap}
      />,
    );

    await user.click(screen.getByLabelText("Helpful"));

    expect(onFeedback).toHaveBeenCalledWith("up");
    expect(onCardTap).not.toHaveBeenCalled();
  });
});
