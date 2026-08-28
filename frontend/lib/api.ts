const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/**
 * Build an absolute API URL from a path.
 *
 * @example api("/trips")        → "http://127.0.0.1:8000/trips"
 * @example api(`/trips/${id}`)  → "http://127.0.0.1:8000/trips/42"
 */
export function api(path: string): string {
  return `${API_BASE}${path}`;
}
