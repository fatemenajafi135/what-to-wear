import { describe, expect, it, vi } from "vitest";
import { signOutAndClearCache } from "./signOut";
import { API_DATA_CACHE, PHOTOS_CACHE } from "@/lib/serviceWorker/cacheNames";

function fakeSupabase(): { auth: { signOut: ReturnType<typeof vi.fn> } } {
  return { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } };
}

describe("signOutAndClearCache", () => {
  it("calls supabase.auth.signOut()", async () => {
    const supabase = fakeSupabase();
    await signOutAndClearCache(supabase as never);
    expect(supabase.auth.signOut).toHaveBeenCalledOnce();
  });

  it("deletes exactly the two user-scoped caches, by name", async () => {
    const supabase = fakeSupabase();
    const deleteSpy = vi.fn().mockResolvedValue(true);
    vi.stubGlobal("caches", { delete: deleteSpy });

    await signOutAndClearCache(supabase as never);

    expect(deleteSpy).toHaveBeenCalledWith(API_DATA_CACHE);
    expect(deleteSpy).toHaveBeenCalledWith(PHOTOS_CACHE);
    expect(deleteSpy).toHaveBeenCalledTimes(2);

    vi.unstubAllGlobals();
  });

  it("does not throw when caches is unavailable (older browser / non-secure context)", async () => {
    const supabase = fakeSupabase();
    vi.stubGlobal("caches", undefined);

    await expect(signOutAndClearCache(supabase as never)).resolves.toBeUndefined();

    vi.unstubAllGlobals();
  });
});
