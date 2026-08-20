/**
 * Server-side clearance for search results.
 *
 * The rule this file exists to enforce: what a caller may see is decided here,
 * from a signature the caller cannot forge — never from a query parameter and
 * never in the browser. The main site used to hide restricted rows with a
 * client-side `SEARCH_PUBLIC_RESULTS_ONLY` flag in index.js, which meant the
 * data was one `curl` away the whole time.
 */
import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";

export const PUBLIC_CLEARANCE = 0;
export const LEVEL_10 = 10;

// The realm role that grants level 10. Assign it per user in Keycloak; merely
// holding an account is not enough, since the same realm backs client-portal
// signups.
const CLEARANCE_ROLE = process.env.CLEARANCE_ROLE || "clearance-10";

// bsco-keycloak.fly.dev is the instance actually serving the `blacksheep`
// realm. auth.theofficialblacksheepco.online answers, but returns
// "Realm does not exist" — do not point this at it.
const ISSUER =
  process.env.KEYCLOAK_ISSUER ||
  "https://bsco-keycloak.fly.dev/realms/blacksheep";

let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function keyset() {
  // Built lazily and reused: createRemoteJWKSet caches the fetched keys and
  // re-fetches only on an unknown kid, so a rotated signing key recovers on its
  // own while a normal request never leaves the process.
  if (!jwks) {
    jwks = createRemoteJWKSet(
      new URL(`${ISSUER}/protocol/openid-connect/certs`)
    );
  }
  return jwks;
}

function hasRole(payload: JWTPayload): boolean {
  const realmAccess = payload.realm_access as { roles?: string[] } | undefined;
  if (realmAccess?.roles?.includes(CLEARANCE_ROLE)) return true;

  // Some clients carry the grant as a client role instead of a realm role.
  const resourceAccess = payload.resource_access as
    | Record<string, { roles?: string[] }>
    | undefined;
  if (!resourceAccess) return false;
  return Object.values(resourceAccess).some((r) =>
    r?.roles?.includes(CLEARANCE_ROLE)
  );
}

/**
 * The highest clearance this request may read. Any failure — missing header,
 * bad signature, wrong issuer, expired, no role — degrades to public rather
 * than erroring, so an expired session quietly shows public results instead of
 * breaking the search box.
 */
export async function clearanceFor(
  authHeader: string | null
): Promise<{ level: number; subject?: string; reason?: string }> {
  if (!authHeader?.startsWith("Bearer ")) {
    return { level: PUBLIC_CLEARANCE, reason: "no bearer token" };
  }

  const token = authHeader.slice("Bearer ".length).trim();
  if (!token) return { level: PUBLIC_CLEARANCE, reason: "empty token" };

  try {
    const { payload } = await jwtVerify(token, keyset(), { issuer: ISSUER });
    if (!hasRole(payload)) {
      return {
        level: PUBLIC_CLEARANCE,
        subject: payload.sub,
        reason: `missing role ${CLEARANCE_ROLE}`,
      };
    }
    return { level: LEVEL_10, subject: payload.sub };
  } catch (error) {
    return {
      level: PUBLIC_CLEARANCE,
      reason: error instanceof Error ? error.message : "verification failed",
    };
  }
}
