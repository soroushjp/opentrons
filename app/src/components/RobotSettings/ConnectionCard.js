// @flow
// RobotSettings card for wifi status
import { Card, useInterval } from '@opentrons/components'
import * as React from 'react'
import { useDispatch, useSelector } from 'react-redux'

import { CONNECTABLE } from '../../discovery'
import type { ViewableRobot } from '../../discovery/types'
import {
  fetchStatus,
  getInternetStatus,
  getNetworkInterfaces,
} from '../../networking'
import type { Dispatch, State } from '../../types'
import { ConnectionInfo, ConnectionStatusMessage } from './connection'
import { SelectNetwork } from './SelectNetwork'

type Props = {| robot: ViewableRobot |}

const CONNECTIVITY = 'Connectivity'
const STATUS_REFRESH_MS = 5000

export function ConnectionCard(props: Props): React.Node {
  const { robot } = props
  const { name: robotName, status, local } = robot
  const dispatch = useDispatch<Dispatch>()
  const internetStatus = useSelector((state: State) =>
    getInternetStatus(state, robotName)
  )
  const { wifi, ethernet } = useSelector((state: State) =>
    getNetworkInterfaces(state, robotName)
  )
  const disabled = status !== CONNECTABLE

  useInterval(() => dispatch(fetchStatus(robotName)), STATUS_REFRESH_MS, true)

  return (
    <Card key={robotName} title={CONNECTIVITY} disabled={disabled}>
      <ConnectionStatusMessage
        type={local ? 'USB' : 'Wi-Fi'}
        status={internetStatus}
      />
      <ConnectionInfo connection={wifi} title="Wi-Fi" disabled={disabled}>
        <SelectNetwork robotName={robotName} />
      </ConnectionInfo>
      <ConnectionInfo
        connection={ethernet}
        title="USB"
        wired
        disabled={disabled}
      />
    </Card>
  )
}
