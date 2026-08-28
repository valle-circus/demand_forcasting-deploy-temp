# Supply Planning Web

Minimal React/TypeScript/Vite/Tailwind shell for the internal maintainer UI.
It intentionally contains no planning calculations and no final page/UX
decisions.

```powershell
Copy-Item .env.example .env.local
pnpm install
pnpm dev
```

Local development proxies `/api` to `http://localhost:8000`. For Vercel, set:

- `VITE_API_BASE_URL` to the Render API URL;
- `VITE_SUPABASE_URL` to the browser-safe Supabase project URL; and
- `VITE_SUPABASE_PUBLISHABLE_KEY` to the browser-safe publishable key.

Never place `SUPABASE_SECRET_KEY` or another elevated credential in this
directory or in a `VITE_` variable.
