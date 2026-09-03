/**
 * Which email domains may hold an account.
 *
 * This copy exists to tell someone why the form rejected them before they wait
 * on a round trip. It is not the gate. The browser holds only a publishable
 * key and calls Supabase Auth directly, so anyone can bypass this file
 * entirely; the enforced copies are the `auth.users` trigger in migration
 * `202609030006` and `ALLOWED_EMAIL_DOMAINS` in the API. Keep all three in
 * step — a domain added here alone will pass the form and then fail at sign-up.
 */

const FALLBACK_DOMAINS = ['circuskitchens.com'] as const

function parse(configured: string | undefined): readonly string[] {
  const source =
    configured && configured.trim().length > 0
      ? configured.split(',')
      : FALLBACK_DOMAINS
  const domains = source
    .map((domain) => domain.trim().toLowerCase().replace(/^@/, ''))
    .filter((domain) => domain.length > 0)
  // A misconfigured variable must not silently widen the hint to "anything".
  return domains.length > 0 ? domains : FALLBACK_DOMAINS
}

export const allowedEmailDomains = parse(
  import.meta.env.VITE_ALLOWED_EMAIL_DOMAINS,
)

export function emailDomainAllowed(email: string): boolean {
  const trimmed = email.trim().toLowerCase()
  const separator = trimmed.lastIndexOf('@')
  if (separator < 1 || separator === trimmed.length - 1) {
    return false
  }
  return allowedEmailDomains.includes(trimmed.slice(separator + 1))
}

/** e.g. "@circuskitchens.com" or "@a.com or @b.com", for form copy. */
export function allowedEmailDomainsLabel(): string {
  const labelled = allowedEmailDomains.map((domain) => `@${domain}`)
  if (labelled.length === 1) {
    return labelled[0]
  }
  return `${labelled.slice(0, -1).join(', ')} or ${labelled[labelled.length - 1]}`
}
