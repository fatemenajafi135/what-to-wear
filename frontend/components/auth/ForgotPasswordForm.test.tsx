import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ForgotPasswordForm } from "./ForgotPasswordForm";

const resetPasswordForEmail = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { resetPasswordForEmail } }),
}));

beforeEach(() => {
  resetPasswordForEmail.mockClear();
});

describe("ForgotPasswordForm", () => {
  it("shows the same confirmation state in place, whether or not the email is registered", async () => {
    resetPasswordForEmail.mockResolvedValue({ error: null });
    render(<ForgotPasswordForm />);

    await userEvent.type(screen.getByLabelText("Email"), "maybe-registered@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    await waitFor(() =>
      expect(
        screen.getByText((_, node) => node?.textContent === "Check your inbox: if an account exists for maybe-registered@example.com, a reset link is on its way."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute("href", "/signin");
  });

  it("renders the error banner and stays on the form when the send request itself fails", async () => {
    resetPasswordForEmail.mockResolvedValue({ error: { message: "network error" } });
    render(<ForgotPasswordForm />);

    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Send reset link" }));

    await waitFor(() =>
      expect(screen.getByText("Something went wrong sending that email. Try again in a moment.")).toBeInTheDocument(),
    );
    expect(screen.queryByRole("link", { name: "Back to sign in" })).not.toBeInTheDocument();
  });
});
