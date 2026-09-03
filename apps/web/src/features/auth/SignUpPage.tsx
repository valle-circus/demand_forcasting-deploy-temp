import { useId, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

import { useAuth } from '@/app/auth/authContext'
import { ApiStatusLine } from '@/components/ApiStatusLine'
import { BrandMark } from '@/components/BrandMark'
import { Button } from '@/components/ui/button'
import {
  allowedEmailDomainsLabel,
  emailDomainAllowed,
} from '@/lib/emailDomains'
import { errorMessage } from '@/lib/errors'

const FIELD_CLASS =
  'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none'

/**
 * Supabase's own default floor is six characters. Eight is required here
 * because every account this form creates is a full maintainer.
 */
const MINIMUM_PASSWORD_LENGTH = 8

type FieldName = 'email' | 'password' | 'confirmation'

/**
 * Self-service sign-up, limited to approved company email domains.
 *
 * The domain check below is a courtesy that saves a round trip, not a control:
 * the browser talks to Supabase Auth directly, so the enforced copies are the
 * `auth.users` trigger and the API's own check. See `lib/emailDomains`.
 */
export function SignUpPage() {
  const { status, signUp } = useAuth()
  const emailId = useId()
  const passwordId = useId()
  const confirmationId = useId()
  const errorId = useId()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [fieldErrors, setFieldErrors] = useState<
    Partial<Record<FieldName, string>>
  >({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmationSent, setConfirmationSent] = useState(false)

  if (status === 'signed-in') {
    return <Navigate to="/overview" replace />
  }

  function validate(field: FieldName): string | undefined {
    if (field === 'email') {
      if (email.trim().length === 0) {
        return 'Enter your work email address.'
      }
      if (!emailDomainAllowed(email)) {
        return `Use your ${allowedEmailDomainsLabel()} address.`
      }
      return undefined
    }
    if (field === 'password') {
      if (password.length < MINIMUM_PASSWORD_LENGTH) {
        return `Use at least ${String(MINIMUM_PASSWORD_LENGTH)} characters.`
      }
      return undefined
    }
    if (confirmation !== password) {
      return 'Both passwords must match.'
    }
    return undefined
  }

  /** Validate on blur, not on every keystroke. */
  function handleBlur(field: FieldName) {
    setFieldErrors((current) => ({ ...current, [field]: validate(field) }))
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) {
      return
    }
    const nextErrors: Partial<Record<FieldName, string>> = {
      email: validate('email'),
      password: validate('password'),
      confirmation: validate('confirmation'),
    }
    setFieldErrors(nextErrors)
    if (Object.values(nextErrors).some((message) => message !== undefined)) {
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      const outcome = await signUp(email, password)
      if (outcome === 'confirmation-sent') {
        setConfirmationSent(true)
      }
      // A 'signed-in' outcome needs nothing here: the session change redirects
      // through the `status` check above.
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <BrandMark />

        {status === 'unconfigured' ? (
          <div role="status" className="mt-6 rounded-lg border border-border p-4">
            <h1 className="text-base font-medium">
              Authentication is not configured
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              This build has no Supabase values, so there is no account to
              create.
            </p>
          </div>
        ) : confirmationSent ? (
          <div role="status">
            <h1 className="mt-6 text-3xl font-semibold tracking-tight">
              Check your email
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              We sent a confirmation link to {email.trim()}. Open it to finish
              creating your account.
            </p>
            <p className="mt-4 text-sm text-muted-foreground">
              Already confirmed?{' '}
              <Link to="/sign-in" className="underline underline-offset-4">
                Sign in
              </Link>
            </p>
          </div>
        ) : (
          <>
            <h1 className="mt-6 text-3xl font-semibold tracking-tight">
              Create account
            </h1>

            <form
              className="mt-6 space-y-4"
              onSubmit={(event) => void handleSubmit(event)}
              noValidate
            >
              <div>
                <label htmlFor={emailId} className="mb-1 block text-sm font-medium">
                  Email
                </label>
                <input
                  id={emailId}
                  type="email"
                  name="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value)
                  }}
                  onBlur={() => {
                    handleBlur('email')
                  }}
                  aria-describedby={
                    fieldErrors.email === undefined
                      ? `${emailId}-hint`
                      : `${emailId}-error`
                  }
                  aria-invalid={fieldErrors.email === undefined ? undefined : true}
                  className={FIELD_CLASS}
                />
                {fieldErrors.email === undefined ? (
                  <p
                    id={`${emailId}-hint`}
                    className="mt-1 text-sm text-muted-foreground"
                  >
                    Use your {allowedEmailDomainsLabel()} address.
                  </p>
                ) : (
                  <p id={`${emailId}-error`} className="mt-1 text-sm text-danger">
                    {fieldErrors.email}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor={passwordId}
                  className="mb-1 block text-sm font-medium"
                >
                  Password
                </label>
                <input
                  id={passwordId}
                  type="password"
                  name="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value)
                  }}
                  onBlur={() => {
                    handleBlur('password')
                  }}
                  aria-describedby={
                    fieldErrors.password === undefined
                      ? `${passwordId}-hint`
                      : `${passwordId}-error`
                  }
                  aria-invalid={
                    fieldErrors.password === undefined ? undefined : true
                  }
                  className={FIELD_CLASS}
                />
                {fieldErrors.password === undefined ? (
                  <p
                    id={`${passwordId}-hint`}
                    className="mt-1 text-sm text-muted-foreground"
                  >
                    At least {MINIMUM_PASSWORD_LENGTH} characters.
                  </p>
                ) : (
                  <p
                    id={`${passwordId}-error`}
                    className="mt-1 text-sm text-danger"
                  >
                    {fieldErrors.password}
                  </p>
                )}
              </div>

              <div>
                <label
                  htmlFor={confirmationId}
                  className="mb-1 block text-sm font-medium"
                >
                  Confirm password
                </label>
                <input
                  id={confirmationId}
                  type="password"
                  name="confirmPassword"
                  autoComplete="new-password"
                  required
                  value={confirmation}
                  onChange={(event) => {
                    setConfirmation(event.target.value)
                  }}
                  onBlur={() => {
                    handleBlur('confirmation')
                  }}
                  aria-describedby={
                    fieldErrors.confirmation === undefined
                      ? undefined
                      : `${confirmationId}-error`
                  }
                  aria-invalid={
                    fieldErrors.confirmation === undefined ? undefined : true
                  }
                  className={FIELD_CLASS}
                />
                {fieldErrors.confirmation !== undefined && (
                  <p
                    id={`${confirmationId}-error`}
                    className="mt-1 text-sm text-danger"
                  >
                    {fieldErrors.confirmation}
                  </p>
                )}
              </div>

              {error !== null && (
                <p id={errorId} role="alert" className="text-sm text-danger">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={submitting}
              >
                {submitting ? 'Creating account' : 'Create account'}
              </Button>
            </form>

            <p className="mt-4 text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link to="/sign-in" className="underline underline-offset-4">
                Sign in
              </Link>
            </p>
          </>
        )}

        <div className="mt-6 border-t border-border pt-3">
          <ApiStatusLine />
        </div>
      </div>
    </main>
  )
}
