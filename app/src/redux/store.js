// TODO: BC 2021-02-03 this file should be typed, once redux concerns are in ts
// initialize redux store and plug in middleware
import { createStore, applyMiddleware, compose } from 'redux'
import thunk from 'redux-thunk'

import { routerMiddleware } from 'connected-react-router'
import { createEpicMiddleware } from 'redux-observable'

import { apiClientMiddleware as robotApiMiddleware } from './robot/api-client'
import { rootReducer, history } from './reducer'
import { rootEpic } from './epic'

const epicMiddleware = createEpicMiddleware()

const middleware = applyMiddleware(
  thunk,
  epicMiddleware,
  robotApiMiddleware(),
  routerMiddleware(history)
)

const composeEnhancers =
  (window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ &&
    window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__({ maxAge: 200 })) ||
  compose
export const store = createStore(rootReducer, composeEnhancers(middleware))

epicMiddleware.run(rootEpic)

// attach store to window if devtools are on once config initializes
const unsubscribe = store.subscribe(() => {
  const { config } = store.getState()
  if (config !== null) {
    if (config.devtools) window.store = store
    unsubscribe()
  }
})
