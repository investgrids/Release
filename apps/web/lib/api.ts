export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

/** How long a server-side API response may be reused before the next render refetches it. This used to be "no-store", so every render of an overview page called the backend. */
export const DEFAULT_REVALIDATE_S = 60;

/**
 * Server-side fetch of a backend endpoint, cached by Next's data cache for `revalidate` seconds (default 60) so repeated renders and crawler hits do not each reach the backend.
 * Pass `{ revalidate: 0 }` for data that must be fetched fresh every time.
 */
export async function fetchAPI<T = unknown>(path: string, opts: { revalidate?: number } = {}): Promise<T> {
  const revalidate = opts.revalidate ?? DEFAULT_REVALIDATE_S;
  const response = await fetch(`${API_BASE_URL}${path}`, revalidate > 0 ? { next: { revalidate } } : { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to fetch ${path}: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
