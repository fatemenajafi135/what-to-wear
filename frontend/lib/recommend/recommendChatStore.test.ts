import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn() },
}));

import { apiClient } from "@/lib/api/client";
import { getState, hydrate, reset, sendTurn, startStyling, subscribe } from "./recommendChatStore";

const mockOutfit = {
  id: null,
  occasion: "business casual",
  rationale_text: "A relaxed pairing that works well here.",
  items: [],
  match_label: "great",
  meta_line: "business casual · Business casual",
};

function turnResponse(overrides: Partial<{ thread_id: string; reply_text: string | null }> = {}) {
  return {
    data: {
      thread_id: "thread-1",
      reply_text: "Got it — what's the occasion?",
      occasion: null,
      formality: null,
      mood: null,
      temp_c: null,
      location: null,
      ...overrides,
    },
    error: undefined,
    response: new Response(),
  };
}

function stylingResponse() {
  return {
    data: {
      thread_id: "thread-1",
      reply_text: null,
      wrap_up_text: "Styling for business casual.",
      outfits: [mockOutfit],
    },
    error: undefined,
    response: new Response(),
  };
}

describe("recommendChatStore", () => {
  beforeEach(() => {
    reset();
    vi.mocked(apiClient.POST).mockReset();
  });

  it("sendTurn success appends a user message + assistant reply and sets threadId from the response", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);

    await sendTurn("business casual");

    const state = getState();
    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({ role: "user", text: "business casual" });
    expect(state.messages[1]).toMatchObject({ role: "assistant", replyText: "Got it — what's the occasion?" });
    expect(state.threadId).toBe("thread-1");
    expect(state.pendingTexts).toEqual(["business casual"]);
    expect(state.turnPending).toBe(false);
  });

  it("sendTurn failure leaves messages/pendingTexts as sent, adds no assistant bubble", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
      response: new Response(null, { status: 500 }),
    } as never);

    await sendTurn("business casual");

    const state = getState();
    // The user's own message is still recorded (it was sent) — only the
    // reply is missing, matching "no bubble invented for it" (research.md §9).
    expect(state.messages).toEqual([expect.objectContaining({ role: "user", text: "business casual" })]);
    expect(state.pendingTexts).toEqual(["business casual"]);
    expect(state.turnPending).toBe(false);
  });

  it("startStyling success appends the wrap-up + outfit message and clears pendingTexts", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);
    await sendTurn("business casual");
    vi.mocked(apiClient.POST).mockResolvedValue(stylingResponse() as never);

    await startStyling();

    const state = getState();
    expect(state.pendingTexts).toEqual([]);
    expect(state.startStyling).toBe("idle");
    const [, , wrapUp, outfitMessage] = state.messages;
    expect(wrapUp).toMatchObject({ role: "assistant", replyText: "Styling for business casual." });
    expect(outfitMessage).toMatchObject({ role: "assistant", outfits: [mockOutfit] });
  });

  it("startStyling failure sets startStyling to error and leaves pendingTexts intact for retry", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);
    await sendTurn("business casual");
    vi.mocked(apiClient.POST).mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
      response: new Response(null, { status: 500 }),
    } as never);

    await startStyling();

    const state = getState();
    expect(state.startStyling).toBe("error");
    expect(state.pendingTexts).toEqual(["business casual"]);
  });

  it("startStyling is a no-op with nothing pending", async () => {
    await startStyling();
    expect(apiClient.POST).not.toHaveBeenCalled();
    expect(getState().startStyling).toBe("idle");
  });

  it("hydrate replaces messages/threadId wholesale and resets the rest", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);
    await sendTurn("business casual");

    hydrate("resumed-thread", [{ id: "m1", role: "user", text: "Rainy commute" }]);

    const state = getState();
    expect(state.threadId).toBe("resumed-thread");
    expect(state.messages).toEqual([{ id: "m1", role: "user", text: "Rainy commute" }]);
    expect(state.pendingTexts).toEqual([]);
    expect(state.turnPending).toBe(false);
    expect(state.startStyling).toBe("idle");
  });

  it("reset clears every field", async () => {
    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);
    await sendTurn("business casual");

    reset();

    expect(getState()).toEqual({
      messages: [],
      pendingTexts: [],
      threadId: null,
      turnPending: false,
      startStyling: "idle",
    });
  });

  it("FR-007: a listener that subscribes only after the action started still observes its eventual result", async () => {
    let resolveTurn!: (value: unknown) => void;
    vi.mocked(apiClient.POST).mockReturnValue(new Promise((resolve) => (resolveTurn = resolve)) as never);

    // Simulate "no component mounted" — the action is kicked off with no
    // subscriber at all, exactly like a request that outlives an unmount.
    const sendPromise = sendTurn("business casual");
    expect(getState().turnPending).toBe(true);

    // A fresh subscriber only shows up later (a remounted RecommendChat).
    const listener = vi.fn();
    subscribe(listener);

    resolveTurn(turnResponse());
    await sendPromise;

    expect(listener).toHaveBeenCalled();
    const state = getState();
    expect(state.turnPending).toBe(false);
    expect(state.messages).toHaveLength(2);
  });

  it("US3/FR-002: never writes to localStorage, sessionStorage, or document.cookie — JS memory only", async () => {
    const localSetItem = vi.spyOn(window.localStorage, "setItem");
    const sessionSetItem = vi.spyOn(window.sessionStorage, "setItem");
    const cookieSetter = vi.spyOn(document, "cookie", "set");

    vi.mocked(apiClient.POST).mockResolvedValue(turnResponse() as never);
    await sendTurn("business casual");
    vi.mocked(apiClient.POST).mockResolvedValue(stylingResponse() as never);
    await startStyling();
    hydrate("resumed-thread", [{ id: "m1", role: "user", text: "Rainy commute" }]);
    reset();

    // A real reload must reset the conversation (FR-002) — that only holds
    // if nothing here ever persists past the JS context that holds `state`.
    expect(localSetItem).not.toHaveBeenCalled();
    expect(sessionSetItem).not.toHaveBeenCalled();
    expect(cookieSetter).not.toHaveBeenCalled();
  });
});
