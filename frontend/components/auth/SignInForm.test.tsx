import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SignInForm } from "./SignInForm";

const push = vi.fn();
const refresh = vi.fn();
const signInWithPassword = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({ auth: { signInWithPassword } }),
}));

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
  signInWithPassword.mockClear();
});

describe("SignInForm", () => {
  it("submits email and password and redirects on success", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    render(<SignInForm />);

    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correcthorse");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(signInWithPassword).toHaveBeenCalledWith({ email: "user@example.com", password: "correcthorse" }),
    );
    expect(push).toHaveBeenCalledWith("/recommend");
  });

  it("renders a single form-level Banner on a bad credential pair, not a field-level error", async () => {
    signInWithPassword.mockResolvedValue({ error: { message: "invalid_credentials" } });
    render(<SignInForm />);

    await userEvent.type(screen.getByLabelText("Email"), "user@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrongpassword");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(screen.getByText("That email and password don't match. Try again or reset your password.")).toBeInTheDocument(),
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("links to /forgot-password and /signup", () => {
    render(<SignInForm />);
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/forgot-password");
    expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute("href", "/signup");
  });
});
