import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RecommendPage from "./page";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    GET: vi.fn((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: false, missing: [] } })
        : Promise.resolve({ data: { picked: false, event: null } }),
    ),
    POST: vi.fn(),
  },
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

  it("renders the hero state on first load", async () => {
    render(<RecommendPage />);
    expect(await screen.findByText("What to Wear")).toBeInTheDocument();
    expect(screen.getByText("Rainy day commute")).toBeInTheDocument();
  });
});
