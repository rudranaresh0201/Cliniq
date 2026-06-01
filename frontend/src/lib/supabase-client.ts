import { createClient } from '@supabase/supabase-js';

const url = (import.meta.env.VITE_SUPABASE_URL as string | undefined)
  ?? 'https://pcbezwbecvitlhznqtqg.supabase.co';

const key = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined)
  ?? 'sb_publishable_MCRNp7znp7q-kxvaBYZP1w_PHco3i0o';

export const supabase = createClient(url, key);
