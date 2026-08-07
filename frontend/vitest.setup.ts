import "@testing-library/jest-dom/vitest";

// jsdom has no `matchMedia` implementation at all — every test gets a safe
// "no match" default (mobile-tier behavior) unless a test overrides it for
// a specific query (e.g. the desktop-tier pager mechanics, SuggestionPager
// feature 009).
if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// jsdom has no ResizeObserver either (RecommendChat measures its fixed
// footer's height to pad the scrollable message list below it) — a no-op
// stand-in is enough for tests, which don't assert on measured layout.
if (typeof window !== "undefined" && !window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
