// Supabase client for the Expo app. Auth (login/session) is handled here; the
// JWT it issues is sent to the Flask API (see lib/api.ts), which verifies it.
import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    'Supabase env vars missing. Copy mobile/.env.example to mobile/.env and fill in.'
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: AsyncStorage,        // persist the session on the device
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,    // not a web-redirect auth flow
  },
});
