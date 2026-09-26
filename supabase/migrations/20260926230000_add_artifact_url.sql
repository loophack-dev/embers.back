-- Stable URL of a ready artifact: {PUBLIC_API_URL}/artifacts/{id}/download.
-- It never expires; the backend redirects to a fresh signed URL on each request.
alter table public.artifacts add column url text;
