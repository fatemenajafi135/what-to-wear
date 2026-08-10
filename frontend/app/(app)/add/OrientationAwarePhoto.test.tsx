import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OrientationAwarePhoto } from "./OrientationAwarePhoto";

function setNaturalSize(img: HTMLImageElement, width: number, height: number) {
  Object.defineProperty(img, "naturalWidth", { value: width, configurable: true });
  Object.defineProperty(img, "naturalHeight", { value: height, configurable: true });
}

describe("OrientationAwarePhoto", () => {
  it("defaults to the square (portrait) treatment before the image loads", () => {
    render(<OrientationAwarePhoto src="blob:fake" />);

    const img = screen.getByRole("presentation") as HTMLImageElement;
    expect(img.className).toContain("portrait");
    expect(img.className).not.toContain("natural");
  });

  it("switches to the natural (uncropped) treatment for a landscape photo", () => {
    render(<OrientationAwarePhoto src="blob:fake" />);
    const img = screen.getByRole("presentation") as HTMLImageElement;

    setNaturalSize(img, 800, 400);
    fireEvent.load(img);

    expect(img.className).toContain("natural");
    expect(img.className).not.toContain("portrait");
  });

  it("switches to the natural treatment for a square photo (not cropped)", () => {
    render(<OrientationAwarePhoto src="blob:fake" />);
    const img = screen.getByRole("presentation") as HTMLImageElement;

    setNaturalSize(img, 500, 500);
    fireEvent.load(img);

    expect(img.className).toContain("natural");
  });

  it("stays on the square-crop treatment for a portrait photo", () => {
    render(<OrientationAwarePhoto src="blob:fake" />);
    const img = screen.getByRole("presentation") as HTMLImageElement;

    setNaturalSize(img, 400, 800);
    fireEvent.load(img);

    expect(img.className).toContain("portrait");
  });

  // Feature 018 (photo-to-items, research.md §4): the region-crop fallback
  // shown before an isolated image exists for a detection, or when
  // isolation failed. Resolution-independent math — see the component's
  // own docstring for the derivation.
  describe("region crop", () => {
    it("renders the default (whole-photo) treatment identically when region is the full frame", () => {
      render(<OrientationAwarePhoto src="blob:fake" region={{ x: 0, y: 0, width: 1, height: 1 }} />);

      const img = screen.getByRole("presentation") as HTMLImageElement;
      expect(img.className).toContain("portrait");
      expect(img.style.position).not.toBe("absolute");
    });

    it("scales and offsets the image to fill the crop frame with just the requested region", () => {
      const { container } = render(
        <OrientationAwarePhoto src="blob:fake" region={{ x: 0.5, y: 0, width: 0.5, height: 0.5 }} />
      );

      const img = container.querySelector("img") as HTMLImageElement;
      // width/height: 100/region.width, 100/region.height — left/top:
      // -100*region.x/region.width, -100*region.y/region.height.
      expect(img.style.width).toBe("200%");
      expect(img.style.height).toBe("200%");
      expect(img.style.left).toBe("-100%");
      expect(img.style.top).toBe("0%");
    });

    it("picks the crop frame's orientation from the CROPPED region, not the whole photo", () => {
      render(<OrientationAwarePhoto src="blob:fake" region={{ x: 0, y: 0, width: 0.25, height: 1 }} />);
      const img = screen.getByRole("presentation") as HTMLImageElement;

      // A wide landscape photo (1600x800) whose left quarter is cropped
      // out (400x800 effective) is a portrait crop, even though the whole
      // photo itself is landscape.
      setNaturalSize(img, 1600, 800);
      fireEvent.load(img);

      const frame = img.closest("div");
      expect(frame?.className).toContain("portrait");
    });
  });
});
