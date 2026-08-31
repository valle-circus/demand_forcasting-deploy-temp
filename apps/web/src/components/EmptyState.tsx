import { Link } from 'react-router-dom'



interface EmptyStateProps {
  title: string
  /** One line. If it needs a paragraph, the screen is wrong. */
  description: string
  /** Required: an empty state with nowhere to go is a dead end. */
  action: { label: string; to: string }
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-border px-6 py-10 text-center">
      <h2 className="text-base font-medium">{title}</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        {description}
      </p>
      {/* A styled link rather than a Button rendering one: this navigates, so
          it should be a link to assistive technology and to middle-click. */}
      <Link
        to={action.to}
        className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none"
      >
        {action.label}
      </Link>
    </div>
  )
}
