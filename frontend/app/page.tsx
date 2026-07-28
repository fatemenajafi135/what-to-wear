import { redirect } from "next/navigation";

/**
 * spec.md FR-015: no real auth exists in this slice, so every visitor is
 * treated as signed in for stub purposes. The signed-out branch (→
 * /signin) is out of scope until feature 002 ships (see spec.md Assumptions).
 */
export default function RootPage() {
  redirect("/recommend");
}
