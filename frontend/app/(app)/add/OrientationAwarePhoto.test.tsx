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
});
