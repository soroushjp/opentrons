// @flow
import { Icon, ListItem } from '@opentrons/components'
import * as React from 'react'

import styles from './upload-panel.css'

export function UploadMenu(): React.Node {
  return (
    <ol className={styles.menu_list}>
      <ListItem
        url="/upload/file-info"
        className={styles.menu_item}
        activeClassName={styles.active}
      >
        <span>File Overview</span>
        <Icon name="chevron-right" className={styles.menu_icon} />
      </ListItem>
    </ol>
  )
}
