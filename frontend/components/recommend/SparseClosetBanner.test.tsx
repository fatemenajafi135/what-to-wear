import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SparseClosetBanner } from "./SparseClosetBanner";

describe("SparseClosetBanner", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("renders when not dismissed", () => {
    render(<SparseClosetBanner />);
    expect(screen.getByText(/working with a small closet/)).toBeInTheDocument();
  });

  it("dismiss hides it and sets the sessionStorage flag", async () => {
    render(<SparseClosetBanner />);
    await userEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByText(/working with a small closet/)).not.toBeInTheDocument();
    expect(sessionStorage.getItem("wtw_sparse_closet_banner_dismissed")).toBe("1");
  });

  it("does not render again within the same (mocked) session", () => {
    sessionStorage.setItem("wtw_sparse_closet_banner_dismissed", "1");
    render(<SparseClosetBanner />);
    expect(screen.queryByText(/working with a small closet/)).not.toBeInTheDocument();
  });
});
