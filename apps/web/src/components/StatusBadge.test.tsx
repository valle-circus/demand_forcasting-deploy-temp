import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it.each(['ready', 'warning', 'running', 'neutral'] as const)(
    'keeps the %s tone outlined',
    (tone) => {
      render(<StatusBadge tone={tone} label={tone} />)

      const badge = screen.getByText(tone)
      expect(badge).toHaveClass('border', 'border-border', 'bg-card')
      expect(badge.className).not.toContain('-soft')
    },
  )

  it('reserves the tinted fill for blocking states', () => {
    render(<StatusBadge tone="blocked" label="Blocked" />)

    expect(screen.getByText('Blocked')).toHaveClass(
      'border-danger-soft',
      'bg-danger-soft',
      'text-danger',
    )
  })
})
