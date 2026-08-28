import { cookies } from "next/headers";
import { USER_ID_COOKIE } from "@/lib/constants";

/**
 * The middleware guarantees this cookie on every request, so a missing value
 * here means middleware didn't run (e.g. a matcher mismatch) rather than a
 * first-time visitor.
 */
export async function getUserId(): Promise<string | null> {
  const store = await cookies();
  return store.get(USER_ID_COOKIE)?.value ?? null;
}
