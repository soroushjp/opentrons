// @flow
// filter labware by manufacturer
import { SelectField } from '@opentrons/components'
import * as React from 'react'
import type { ContextRouter } from 'react-router-dom'
import { withRouter } from 'react-router-dom'

import { buildFiltersUrl, getAllManufacturers } from '../../filters'
import { MANUFACTURER, MANUFACTURER_VALUES } from '../../localization'
import type { FilterParams } from '../../types'
import styles from './styles.css'

export type FilterManufacturerProps = {|
  ...ContextRouter,
  filters: FilterParams,
|}

export function FilterManufacturerComponent(
  props: FilterManufacturerProps
): React.Node {
  const { history, filters } = props
  const manufacturers = getAllManufacturers()
  const options = manufacturers.map(value => ({
    value,
    label: MANUFACTURER_VALUES[value] || value,
  }))

  return (
    <label className={styles.filter_manufacturer}>
      <p className={styles.filter_label}>{MANUFACTURER}</p>
      <SelectField
        className={styles.filter_manufacturer_select}
        name="manufacturer"
        value={filters.manufacturer}
        options={options}
        onValueChange={(_, value) => {
          if (value) {
            history.push(buildFiltersUrl({ ...filters, manufacturer: value }))
          }
        }}
      />
    </label>
  )
}

export const FilterManufacturer: React.AbstractComponent<
  $Diff<FilterManufacturerProps, ContextRouter>
> = withRouter(FilterManufacturerComponent)
