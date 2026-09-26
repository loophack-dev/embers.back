-- artifacts.url now stores the Supabase Storage signed URL; this is when it expires.
alter table public.artifacts add column url_expires_at timestamptz;
