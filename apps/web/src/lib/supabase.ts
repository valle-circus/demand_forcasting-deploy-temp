import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim()
const supabasePublishableKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim()

export const browserSupabaseConfigured = Boolean(
  supabaseUrl && supabasePublishableKey,
)

let client: SupabaseClient | null = null

export function getSupabaseClient(): SupabaseClient | null {
  if (!browserSupabaseConfigured) {
    return null
  }
  if (client === null) {
    client = createClient(supabaseUrl!, supabasePublishableKey!)
  }
  return client
}
