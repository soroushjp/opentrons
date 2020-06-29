// @flow
import type { WellGroup } from '@opentrons/components'
import { LabeledValue, Modal, OutlineButton } from '@opentrons/components'
import type {
  LabwareDefinition2,
  PipetteNameSpecs,
} from '@opentrons/shared-data'
import { sortWells } from '@opentrons/shared-data'
import cx from 'classnames'
import omit from 'lodash/omit'
import * as React from 'react'
import { useDispatch, useSelector } from 'react-redux'

import type { StepFieldName } from '../../../../form-types'
import { selectors } from '../../../../labware-ingred/selectors'
import type { ContentsByWell } from '../../../../labware-ingred/types'
import { selectors as stepFormSelectors } from '../../../../step-forms'
import { changeFormInput } from '../../../../steplist/actions'
import type { WellIngredientNames } from '../../../../steplist/types'
import * as wellContentsSelectors from '../../../../top-selectors/well-contents'
import { arrayToWellGroup } from '../../../../utils'
import { SelectableLabware, wellFillFromWellContents } from '../../../labware'
import modalStyles from '../../../modals/modal.css'
import { WellSelectionInstructions } from '../../../WellSelectionInstructions'
import styles from './WellSelectionModal.css'

type WellSelectionModalProps = {|
  isOpen: boolean,
  labwareId: ?string,
  name: StepFieldName,
  onCloseClick: (e: ?SyntheticEvent<*>) => mixed,
  pipetteId: ?string,
|}

type WellSelectionModalComponentProps = {|
  deselectWells: WellGroup => mixed,
  handleSave: () => mixed,
  highlightedWells: WellGroup,
  ingredNames: WellIngredientNames,
  labwareDef: ?LabwareDefinition2,
  onCloseClick: (e: ?SyntheticEvent<*>) => mixed,
  pipetteSpec: ?PipetteNameSpecs,
  selectedPrimaryWells: WellGroup,
  selectWells: WellGroup => mixed,
  wellContents: ContentsByWell,
  updateHighlightedWells: WellGroup => mixed,
|}

const WellSelectionModalComponent = (
  props: WellSelectionModalComponentProps
) => {
  const {
    deselectWells,
    handleSave,
    highlightedWells,
    ingredNames,
    labwareDef,
    onCloseClick,
    pipetteSpec,
    selectedPrimaryWells,
    selectWells,
    wellContents,
    updateHighlightedWells,
  } = props

  return (
    <Modal
      className={modalStyles.modal}
      contentsClassName={cx(
        modalStyles.modal_contents,
        modalStyles.transparent_content
      )}
      onCloseClick={onCloseClick}
    >
      <div className={styles.top_row}>
        <LabeledValue
          label="Pipette"
          value={pipetteSpec ? pipetteSpec.displayName : ''}
          className={styles.inverted_text}
        />
        <OutlineButton onClick={handleSave} inverted>
          SAVE SELECTION
        </OutlineButton>
      </div>

      {labwareDef && (
        <SelectableLabware
          labwareProps={{
            showLabels: true,
            definition: labwareDef,
            highlightedWells,
            wellFill: wellFillFromWellContents(wellContents),
          }}
          selectedPrimaryWells={selectedPrimaryWells}
          selectWells={selectWells}
          deselectWells={deselectWells}
          updateHighlightedWells={updateHighlightedWells}
          pipetteChannels={pipetteSpec ? pipetteSpec.channels : null}
          ingredNames={ingredNames}
          wellContents={wellContents}
        />
      )}

      <WellSelectionInstructions />
    </Modal>
  )
}

export const WellSelectionModal = (
  props: WellSelectionModalProps
): React.Node => {
  const { isOpen, labwareId, name, onCloseClick, pipetteId } = props

  const dispatch = useDispatch()

  // selector data
  const allWellContentsForStep = useSelector(
    wellContentsSelectors.getAllWellContentsForActiveItem
  )
  const formData = useSelector(stepFormSelectors.getUnsavedForm)
  const ingredNames = useSelector(selectors.getLiquidNamesById)
  const labwareEntities = useSelector(stepFormSelectors.getLabwareEntities)
  const pipetteEntities = useSelector(stepFormSelectors.getPipetteEntities)

  // selector-derived data
  const labwareDef = (labwareId && labwareEntities[labwareId]?.def) || null
  const pipette = pipetteId != null ? pipetteEntities[pipetteId] : null

  const wellFieldData: ?Array<string> = formData?.[name]
  const initialSelectedPrimaryWells =
    wellFieldData != null ? arrayToWellGroup(wellFieldData) : {}

  // component state
  const [
    selectedPrimaryWells,
    setSelectedPrimaryWells,
  ] = React.useState<WellGroup>(initialSelectedPrimaryWells)
  const [highlightedWells, setHighlightedWells] = React.useState<WellGroup>({})

  // actions
  const saveWellSelection = (wells: WellGroup) =>
    dispatch(
      changeFormInput({
        update: { [name]: Object.keys(wells).sort(sortWells) },
      })
    )

  const selectWells = (wells: WellGroup) => {
    setSelectedPrimaryWells(prev => ({ ...prev, ...wells }))
    setHighlightedWells({})
  }

  const deselectWells = (deselectedWells: WellGroup) => {
    setSelectedPrimaryWells(prev => omit(prev, Object.keys(deselectedWells)))
    setHighlightedWells({})
  }

  const handleSave = () => {
    saveWellSelection(selectedPrimaryWells)
    onCloseClick()
  }

  if (!isOpen) return null

  return (
    <WellSelectionModalComponent
      {...{
        deselectWells,
        handleSave,
        highlightedWells,
        ingredNames,
        labwareDef,
        onCloseClick,
        pipetteSpec: pipette?.spec,
        selectWells,
        selectedPrimaryWells,
        updateHighlightedWells: setHighlightedWells,
        wellContents:
          labwareId != null && allWellContentsForStep != null
            ? allWellContentsForStep[labwareId]
            : {},
      }}
    />
  )
}
