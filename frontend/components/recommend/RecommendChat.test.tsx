import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecommendChat } from "./RecommendChat";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: () => Promise.resolve({ data: { session: { user: { email: "maya@example.com" } } } }) },
  }),
}));

import { apiClient } from "@/lib/api/client";

function mockGetByUrl(url: string) {
  if (url === "/api/v1/recommend/readiness") {
    return Promise.resolve({ data: { ready: true, sparse: false, missing: [] } });
  }
  return Promise.resolve({ data: { picked: false, event: null } });
}

const mockOutfit = {
  rationale_text: "A relaxed pairing that works well here.[1]",
  items: [
    { id: "item-1", name: "Navy tee", category: "t-shirt", category_group: "top", colors: [], color_names: [], photo_url: null },
  ],
  match_label: "great",
};
const mockCitations = [{ number: 1, text: "Casual pieces pair well together." }];

describe("RecommendChat", () => {
  beforeEach(() => {
    vi.mocked(apiClient.POST).mockReset();
    vi.mocked(apiClient.GET).mockReset().mockImplementation(mockGetByUrl as never);
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
  });

  it("full happy path: hero -> compose -> Start styling -> reply with citations and thumbnails", async () => {
    let resolvePost!: (value: unknown) => void;
    vi.mocked(apiClient.POST).mockReturnValue(new Promise((resolve) => (resolvePost = resolve)) as never);

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");

    const startButton = screen.getByText("Start styling");
    expect(startButton).toBeEnabled();
    await userEvent.click(startButton);

    expect(screen.getByText("Thinking…")).toBeInTheDocument();

    resolvePost({
      data: { thread_id: "thread-1", reply_text: null, outfit: mockOutfit, citations: mockCitations },
      error: undefined,
      response: new Response(),
    });

    await waitFor(() => {
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });
    expect(screen.getByText("Casual pieces pair well together.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Navy tee" })).toHaveAttribute("href", "/closet/item-1");

    expect(apiClient.POST).toHaveBeenCalledWith(
      "/api/v1/recommend/messages",
      expect.objectContaining({ body: { message: "business casual", thread_id: null } }),
    );
  });

  it("zero-outfit reply renders reply_text with no thumbnails or citations", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: {
        thread_id: "thread-1",
        reply_text: "Your closet doesn't have enough items to assemble an outfit for this request.",
        outfit: null,
        citations: [],
      },
      error: undefined,
      response: new Response(),
    } as never);

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "black tie gala{Enter}");
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(
        screen.getByText("Your closet doesn't have enough items to assemble an outfit for this request."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Navy tee" })).not.toBeInTheDocument();
  });

  it("error path shows retry, and retry re-issues the same request", async () => {
    vi.mocked(apiClient.POST).mockResolvedValueOnce({
      data: undefined,
      error: { detail: "boom" },
      response: new Response(null, { status: 500 }),
    } as never);

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(screen.getByText("Something went wrong pulling that together.")).toBeInTheDocument();
    });

    vi.mocked(apiClient.POST).mockResolvedValueOnce({
      data: { thread_id: "thread-1", reply_text: null, outfit: mockOutfit, citations: mockCitations },
      error: undefined,
      response: new Response(),
    } as never);

    await userEvent.click(screen.getByText("Try again"));

    await waitFor(() => {
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });
    expect(apiClient.POST).toHaveBeenCalledTimes(2);
    expect(vi.mocked(apiClient.POST).mock.calls[1]?.[1]).toMatchObject({
      body: { message: "business casual", thread_id: null },
    });
  });

  it("Start styling is hidden in the hero state (0 messages)", async () => {
    render(<RecommendChat />);
    await screen.findByLabelText("Message");
    expect(screen.queryByText("Start styling")).not.toBeInTheDocument();
  });

  it("shows the insufficient-closet gate and no composer when the closet isn't ready", async () => {
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: false, sparse: false, missing: ["a pair of shoes"] } })
        : Promise.resolve({ data: { picked: false, event: null } })) as never);

    render(<RecommendChat />);
    expect(await screen.findByText("Add items to your closet")).toBeInTheDocument();
    expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  });

  it("shows the sparse-closet banner when ready but sparse", async () => {
    vi.mocked(apiClient.GET).mockReset().mockImplementation(((url: string) =>
      url === "/api/v1/recommend/readiness"
        ? Promise.resolve({ data: { ready: true, sparse: true, missing: [] } })
        : Promise.resolve({ data: { picked: false, event: null } })) as never);

    render(<RecommendChat />);
    await screen.findByLabelText("Message");
    expect(screen.getByText(/working with a small closet/)).toBeInTheDocument();
  });

  it("US2: a second Start-styling call echoes the first response's thread_id", async () => {
    vi.mocked(apiClient.POST).mockResolvedValueOnce({
      data: { thread_id: "thread-1", reply_text: null, outfit: mockOutfit, citations: mockCitations },
      error: undefined,
      response: new Response(),
    } as never);

    render(<RecommendChat />);
    await userEvent.type(await screen.findByLabelText("Message"), "business casual{Enter}");
    await userEvent.click(screen.getByText("Start styling"));
    await waitFor(() => {
      expect(screen.getByText(/A relaxed pairing that works well here\./)).toBeInTheDocument();
    });

    vi.mocked(apiClient.POST).mockResolvedValueOnce({
      data: { thread_id: "thread-1", reply_text: null, outfit: mockOutfit, citations: mockCitations },
      error: undefined,
      response: new Response(),
    } as never);

    await userEvent.type(await screen.findByLabelText("Message"), "something warmer{Enter}");
    await userEvent.click(screen.getByText("Start styling"));

    await waitFor(() => {
      expect(apiClient.POST).toHaveBeenCalledTimes(2);
    });
    expect(vi.mocked(apiClient.POST).mock.calls[1]?.[1]).toMatchObject({
      body: { message: "something warmer", thread_id: "thread-1" },
    });
  });
});
