import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectedAccountsSection } from "./ConnectedAccountsSection";

describe("ConnectedAccountsSection", () => {
  it("renders Google Calendar in its disconnected, inert appearance", () => {
    render(<ConnectedAccountsSection />);

    expect(screen.getByText("Google Calendar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect" })).toBeDisabled();
  });

  it("renders Weather services with a non-interactive Coming soon badge", () => {
    render(<ConnectedAccountsSection />);

    expect(screen.getByText("Weather services")).toBeInTheDocument();
    expect(screen.getByText("Coming soon")).toBeInTheDocument();
  });

  it("has no Edit/Done control", () => {
    render(<ConnectedAccountsSection />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Done" })).not.toBeInTheDocument();
  });
});
