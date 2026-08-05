import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ItemPhoto } from "./ItemPhoto";

describe("ItemPhoto", () => {
  it("renders NoPhoto when src is falsy", () => {
    const { container } = render(<ItemPhoto src={null} />);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("renders the real <img> when src is present", () => {
    render(<ItemPhoto src="https://storage.example/signed.jpg" alt="A jacket" />);
    expect(screen.getByRole("img", { name: "A jacket" })).toHaveAttribute("src", "https://storage.example/signed.jpg");
  });

  it("falls back to NoPhoto if the image fails to load — an expired signed URL never renders a broken image (docs/design-decisions.md §52)", () => {
    const { container } = render(<ItemPhoto src="https://storage.example/expired.jpg" alt="A jacket" />);
    const img = screen.getByRole("img", { name: "A jacket" });

    fireEvent.error(img);

    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("gives a new src its own chance to load after a previous one failed", () => {
    const { rerender, container } = render(<ItemPhoto src="https://storage.example/expired.jpg" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    fireEvent.error(img!);
    expect(container.querySelector("img")).not.toBeInTheDocument();

    rerender(<ItemPhoto src="https://storage.example/fresh.jpg" />);
    expect(container.querySelector("img")).toHaveAttribute("src", "https://storage.example/fresh.jpg");
  });
});
