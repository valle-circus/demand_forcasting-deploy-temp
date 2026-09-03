-- Self-service sign-up, limited to approved company email domains.
--
-- The browser holds a publishable key and talks to Supabase Auth directly, so
-- the React form's domain check is a courtesy, not a boundary: anyone can post
-- to /auth/v1/signup themselves. This trigger is the boundary that stops the
-- account from existing at all. `SupabaseIdentityVerifier` in the FastAPI
-- service repeats the same check in front of the data, because a project
-- setting changed in the dashboard must not silently reopen the door.
--
-- Keep `allowed_domains` below in step with the API's ALLOWED_EMAIL_DOMAINS.
-- The API value is authoritative for reaching planning data; this one decides
-- whether the Supabase account can be created.

create or replace function public.enforce_signup_email_domain()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  allowed_domains constant text[] := array['circuskitchens.com'];
  candidate_domain text;
begin
  -- A null email is refused rather than ignored: `split_part` on null yields
  -- null, and a null comparison below would pass the row through the gate.
  if new.email is null or position('@' in new.email) = 0 then
    raise exception 'An email address is required to create an account.'
      using errcode = 'check_violation';
  end if;

  candidate_domain := lower(split_part(new.email, '@', 2));

  if not (candidate_domain = any (allowed_domains)) then
    raise exception 'Email domain % is not approved for this application.',
      candidate_domain
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;

comment on function public.enforce_signup_email_domain() is
  'Rejects auth.users inserts whose email domain is not company-approved.';

-- Existing accounts are untouched: the trigger fires on insert only.
drop trigger if exists enforce_signup_email_domain on auth.users;

create trigger enforce_signup_email_domain
before insert on auth.users
for each row
execute function public.enforce_signup_email_domain();
