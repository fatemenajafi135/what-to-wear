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
