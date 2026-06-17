// Thin fetch wrapper that attaches the Supabase JWT as a Bearer token, so the
// Flask API can verify the caller. Base URL is the deployed host by default.
import { supabase } from './supabase';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://thotamaali.com';

// The Render free tier sleeps when idle; a cold start has been measured at up to
// ~130s. We allow 150s so the first call can still succeed through a wake-up, but
// bound it so a truly unreachable server fails with a message, not a forever spin.
const TIMEOUT_MS = 150_000;

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers ?? {}),
      },
    });
  } catch (e: any) {
    if (e?.name === 'AbortError') {
      throw new Error('Server did not respond in time — it may be waking up.');
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}
