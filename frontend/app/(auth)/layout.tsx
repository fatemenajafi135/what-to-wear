import { AuthShell } from "@/components/auth/AuthShell";
import { FocusOnNavigate } from "@/components/shell/FocusOnNavigate";

/**
 * The auth shell — no persistent chrome (design-system.md §4's auth stack).
 * FocusOnNavigate is already generic over any `main h1` (feature 001), so
 * reusing it here moves focus to the wordmark on navigation between the
 * four auth screens, same as it does for the four primary destinations.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthShell>
      <FocusOnNavigate />
      {children}
    </AuthShell>
  );
}
