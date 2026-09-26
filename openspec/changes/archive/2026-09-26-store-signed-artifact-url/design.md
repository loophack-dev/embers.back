# Design

## Decisions

- **D1.** `SupabaseStorage.signed_url` recibe `download_name` opcional: la URL guardada va sin `&download=` (forma exacta de Supabase); el endpoint `/download` sigue usando el nombre legible.
- **D2.** `ArtifactService.create` firma después de subir y llama `mark_ready(storage_path, size_bytes, url, url_expires_at)` en una sola escritura. Si la firma falla, el archivo queda `failed` como cualquier fallo de subida.
- **D3.** `ready_for_task` construye `ArtifactOut` con la URL guardada; si falta o vence en menos de 60 s, firma de nuevo y la persiste con `update_url`.
- **D4.** Se borra `PUBLIC_API_URL` de `Settings`, `.env.example` y README para no dejar configuración muerta.
