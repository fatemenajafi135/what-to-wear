import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HeroState } from "./HeroState";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: () => Promise.resolve({ data: { session: null } }) },
  }),
}));

describe("HeroState", () => {
  it("renders a greeting", async () => {
    render(<HeroState onSuggestionTap={vi.fn()} />);
    expect(await screen.findByText(/Good (morning|afternoon|evening), there/)).toBeInTheDocument();
  });

  it("renders all three suggestion chips", () => {
    render(<HeroState onSuggestionTap={vi.fn()} />);
    expect(screen.getByText("Rainy day commute")).toBeInTheDocument();
    expect(screen.getByText("Dinner date outfit")).toBeInTheDocument();
    expect(screen.getByText("Business casual")).toBeInTheDocument();
  });

  it("tapping a chip calls onSuggestionTap with its text", async () => {
    const onSuggestionTap = vi.fn();
    render(<HeroState onSuggestionTap={onSuggestionTap} />);
    await userEvent.click(screen.getByText("Business casual"));
    expect(onSuggestionTap).toHaveBeenCalledWith("Business casual");
  });
});
