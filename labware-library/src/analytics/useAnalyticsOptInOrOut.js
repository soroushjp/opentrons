// @flow
// A hook for analytics opt in/out components (eg modals or toggles)
// Uses cookie as initial source of truth. Will write a cookie if none exists.
import { useCallback, useEffect, useState } from 'react'

import type { AnalyticsState } from './types'
import {
  getAnalyticsState,
  getDefaultAnalyticsState,
  initializeAnalytics,
  persistAnalyticsState,
} from './utils'

type UseAnalyticsOptInOrOutResult = {|
  setAnalyticsOptIn: boolean => void,
  analyticsState: AnalyticsState,
|}

export const useAnalyticsOptInOrOut = (): UseAnalyticsOptInOrOutResult => {
  const [analyticsState, setAnalyticsState] = useState<AnalyticsState>(
    getDefaultAnalyticsState
  )

  // initialize once using values in cookie (or default initial values, if no cookie)
  useEffect(() => {
    const initialState = getAnalyticsState()

    initializeAnalytics(initialState)
    setAnalyticsState(initialState)
  }, [])

  const setAnalyticsOptIn = useCallback((optedIn: boolean) => {
    const nextState = { seenOptIn: true, optedIn }
    persistAnalyticsState(nextState)
    setAnalyticsState(nextState)
  }, [])

  return { setAnalyticsOptIn, analyticsState }
}
