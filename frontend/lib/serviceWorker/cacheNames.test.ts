import { describe, expect, it } from "vitest";
import { API_DATA_CACHE, PHOTOS_CACHE, USER_SCOPED_CACHE_NAMES } from "./cacheNames";

describe("cacheNames", () => {
  it("USER_SCOPED_CACHE_NAMES is exactly the two user-scoped cache names (contracts/route-caching.md invariant 2)", () => {
    expect(USER_SCOPED_CACHE_NAMES).toEqual([API_DATA_CACHE, PHOTOS_CACHE]);
  });

  it("cache names are non-empty and distinct", () => {
    expect(API_DATA_CACHE).toBeTruthy();
    expect(PHOTOS_CACHE).toBeTruthy();
    expect(API_DATA_CACHE).not.toBe(PHOTOS_CACHE);
  });
});
