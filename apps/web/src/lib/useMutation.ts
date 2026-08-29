/**
 * A small hook for the three write actions in this application: importing a
 * source file, activating a master-data version, and computing a planning run.
 *
 * Its one non-obvious job is **preventing duplicate submission**. The planning
 * run is synchronous, has no job id and no idempotency key, so a second click
 * would start a second calculation. The in-flight guard is a ref rather than
 * the rendered state because a rapid second click can land before React has
 * re-rendered the disabled button.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { isAbort } from './errors'

export type MutationState<T> =
  | { status: 'idle'; data: null; error: null }
  | { status: 'pending'; data: null; error: null }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: null; error: Error }

export interface Mutation<TInput, TResult> {
  state: MutationState<TResult>
  /**
   * Runs the action. Resolves with the result, or `null` when the call was
   * skipped because one was already in flight or the component unmounted.
   * Never rejects — inspect `state.error` instead.
   */
  mutate: (input: TInput) => Promise<TResult | null>
  reset: () => void
  isPending: boolean
}

const IDLE = { status: 'idle', data: null, error: null } as const
const PENDING = { status: 'pending', data: null, error: null } as const

export function useMutation<TInput, TResult>(
  action: (input: TInput) => Promise<TResult>,
): Mutation<TInput, TResult> {
  const [state, setState] = useState<MutationState<TResult>>(IDLE)
  const inFlight = useRef(false)
  const mounted = useRef(true)

  const actionRef = useRef(action)
  useEffect(() => {
    actionRef.current = action
  })

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const mutate = useCallback(async (input: TInput): Promise<TResult | null> => {
    if (inFlight.current) {
      return null
    }
    inFlight.current = true
    setState(PENDING)

    try {
      const data = await actionRef.current(input)
      if (mounted.current) {
        setState({ status: 'success', data, error: null })
      }
      return data
    } catch (error: unknown) {
      if (mounted.current && !isAbort(error)) {
        setState({
          status: 'error',
          data: null,
          error: error instanceof Error ? error : new Error(String(error)),
        })
      }
      return null
    } finally {
      inFlight.current = false
    }
  }, [])

  const reset = useCallback(() => {
    setState(IDLE)
  }, [])

  return { state, mutate, reset, isPending: state.status === 'pending' }
}
