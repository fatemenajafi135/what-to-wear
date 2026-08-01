import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RecommendPage from "./page";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn().mockResolvedValue({ data: { picked: false, event: null } }), POST: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { getSession: () => Promise.resolve({ data: { session: null } }) } }),
}));

describe("RecommendPage", () => {
  it("renders the TopHeader title and subtitle", () => {
    render(<RecommendPage />);
    expect(screen.getByRole("heading", { name: "Styling" })).toBeInTheDocument();
    expect(screen.getByText("Ask for an outfit, get cited picks from your closet")).toBeInTheDocument();
  });

  it("renders the hero state on first load", () => {
    render(<RecommendPage />);
    expect(screen.getByText("What to Wear")).toBeInTheDocument();
    expect(screen.getByText("Rainy day commute")).toBeInTheDocument();
  });
});
