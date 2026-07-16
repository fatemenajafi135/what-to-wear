"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Signed-in users land on their closet (US1 Acceptance Scenario 1: "a
// screen that is theirs alone"); signed-out users never reach this render
// at all -- AuthGuard already redirected to /sign-in before this mounts.
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/closet");
  }, [router]);

  return null;
}
