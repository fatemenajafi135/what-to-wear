import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SessionActions } from "./SessionActions";

describe("SessionActions", () => {
  it("always shows 'Continue conversation', linking to /recommend with the session's own id as thread_id", () => {
    render(<SessionActions sessionId="session-1" outfitCount={0} />);
    expect(screen.getByRole("link", { name: "Continue conversation" })).toHaveAttribute(
      "href",
      "/recommend?thread_id=session-1",
    );
  });

  it("shows the outfit-linked 'View in Outfits' button with the right count when outfit_count > 0", () => {
    render(<SessionActions sessionId="session-1" outfitCount={3} />);
    expect(screen.getByRole("link", { name: "3 → View in Outfits" })).toHaveAttribute("href", "/outfits");
  });

  it("hides the 'View in Outfits' button when the session produced no outfits", () => {
    render(<SessionActions sessionId="session-1" outfitCount={0} />);
    expect(screen.queryByRole("link", { name: /View in Outfits/ })).not.toBeInTheDocument();
  });
});
