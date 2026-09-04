-- Add `circus-group.com` to the self-service sign-up allowlist.
--
-- `circus-group.com` is the company alias colleagues are expected to use, so it
-- becomes the domain the sign-up form nudges towards. `circuskitchens.com`
-- stays approved: existing accounts were created under it and this trigger only
-- fires on insert, but removing it would strand anyone who has to re-register.
--
-- This replaces the function created in 202609030006 rather than editing it,
-- because that migration has already been applied. Keep `allowed_domains` below
-- in step with the API's ALLOWED_EMAIL_DOMAINS and with the browser hint in
-- `apps/web/src/lib/emailDomains.ts`.

create or replace function public.enforce_signup_email_domain()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  allowed_domains constant text[] :=
    array['circus-group.com', 'circuskitchens.com'];
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

-- Recreated so the trigger is guaranteed to point at the replaced function.
drop trigger if exists enforce_signup_email_domain on auth.users;

create trigger enforce_signup_email_domain
before insert on auth.users
for each row
execute function public.enforce_signup_email_domain();
