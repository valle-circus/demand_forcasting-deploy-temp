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
- `VITE_SUPABASE_URL` to the browser-safe Supabase project URL;
- `VITE_SUPABASE_PUBLISHABLE_KEY` to the browser-safe publishable key; and
- `VITE_ALLOWED_EMAIL_DOMAINS` to the comma-separated sign-up domains.

`VITE_ALLOWED_EMAIL_DOMAINS` only tells someone why the sign-up form rejected
their address. It enforces nothing: this bundle ships to the browser and calls
Supabase Auth directly, so the gate is the `auth.users` trigger in
`supabase/migrations/202609030006_signup_email_domain_gate.sql` plus the API's
`ALLOWED_EMAIL_DOMAINS`. Keep all three in step.

Never place `SUPABASE_SECRET_KEY` or another elevated credential in this
directory or in a `VITE_` variable.
