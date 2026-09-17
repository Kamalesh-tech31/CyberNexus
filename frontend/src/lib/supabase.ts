import { createClient, SupabaseClient } from '@supabase/supabase-js';

const env = (typeof import.meta !== 'undefined' && (import.meta as any).env) ? (import.meta as any).env : ((typeof process !== 'undefined' ? process.env : {}) as any);
const supabaseUrl = env?.VITE_SUPABASE_URL || 'https://placeholder-project.supabase.co';
const supabaseAnonKey = 
  env?.VITE_SUPABASE_PUBLISHABLE_KEY || 
  env?.VITE_SUPABASE_ANON_KEY || 
  'placeholder-anon-key';

if (!env?.VITE_SUPABASE_URL || (!env?.VITE_SUPABASE_PUBLISHABLE_KEY && !env?.VITE_SUPABASE_ANON_KEY)) {
  console.warn(
    '[CyberNexus Auth] Supabase URL or Publishable/Anon key missing in environment variables. Google OAuth will be disabled until configured.'
  );
}

/**
 * Singleton Supabase browser client configured with PKCE flow for secure OAuth.
 */
export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce',
  },
});
