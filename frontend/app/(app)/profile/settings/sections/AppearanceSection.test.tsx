import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppearanceSection } from "./AppearanceSection";

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("AppearanceSection", () => {
  it("defaults to Light when nothing is stored", () => {
    render(<AppearanceSection />);

    expect(screen.getByRole("tab", { name: "Light" })).toHaveAttribute("aria-selected", "true");
  });

  it("selecting Dark persists to localStorage and sets data-theme immediately", async () => {
    render(<AppearanceSection />);

    await userEvent.click(screen.getByRole("tab", { name: "Dark" }));

    expect(screen.getByRole("tab", { name: "Dark" })).toHaveAttribute("aria-selected", "true");
    expect(window.localStorage.getItem("wtw-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("selecting System persists and sets data-theme", async () => {
    render(<AppearanceSection />);

    await userEvent.click(screen.getByRole("tab", { name: "System" }));

    expect(window.localStorage.getItem("wtw-theme")).toBe("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("system");
  });

  it("reflects a previously-stored preference on mount", () => {
    window.localStorage.setItem("wtw-theme", "dark");

    render(<AppearanceSection />);

    expect(screen.getByRole("tab", { name: "Dark" })).toHaveAttribute("aria-selected", "true");
  });

  it("has no Edit/Done control", () => {
    render(<AppearanceSection />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Done" })).not.toBeInTheDocument();
  });
});
