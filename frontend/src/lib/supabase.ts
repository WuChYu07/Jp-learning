/**
 * Supabase auth — disabled in single-user mode.
 * Re-enable when AUTH_ENABLED=true and users bring their own Supabase project.
 */
import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const supabaseConfigured = Boolean(url && anonKey);

export const supabase = supabaseConfigured
  ? createClient(url!, anonKey!)
  : null;

export async function signIn(email: string, password: string) {
  if (!supabase) throw new Error("Supabase not configured");
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  if (data.session?.access_token) {
    localStorage.setItem("access_token", data.session.access_token);
  }
  return data;
}

export async function signUp(email: string, password: string) {
  if (!supabase) throw new Error("Supabase not configured");
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw error;
  if (data.session?.access_token) {
    localStorage.setItem("access_token", data.session.access_token);
  }
  return data;
}

export function signOut() {
  localStorage.removeItem("access_token");
  supabase?.auth.signOut();
}
