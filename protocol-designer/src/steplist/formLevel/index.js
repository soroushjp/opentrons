// @flow
import type { StepType } from '../../form-types'
import {
  type FormError,
  blockTemperatureHoldRequired,
  blockTemperatureRequired,
  composeErrors,
  engageHeightRangeExceeded,
  engageHeightRequired,
  incompatibleAspirateLabware,
  incompatibleDispenseLabware,
  incompatibleLabware,
  lidTemperatureHoldRequired,
  lidTemperatureRequired,
  magnetActionRequired,
  moduleIdRequired,
  pauseForTimeOrUntilTold,
  profileTargetLidTempRequired,
  profileVolumeRequired,
  targetTemperatureRequired,
  wellRatioMoveLiquid,
} from './errors'
import {
  type FormWarning,
  type FormWarningType,
  belowPipetteMinimumVolume,
  composeWarnings,
  maxDispenseWellVolume,
  minDisposalVolume,
} from './warnings'

export { handleFormChange } from './handleFormChange'
export { createBlankForm } from './createBlankForm'
export { getDefaultsForStepType } from './getDefaultsForStepType'
export { getDisabledFields } from './getDisabledFields'
export { getNextDefaultPipetteId } from './getNextDefaultPipetteId'
export {
  getNextDefaultTemperatureModuleId,
  getNextDefaultThermocyclerModuleId,
} from './getNextDefaultModuleId'
export { getNextDefaultMagnetAction } from './getNextDefaultMagnetAction'
export { getNextDefaultEngageHeight } from './getNextDefaultEngageHeight'
export {
  getNextDefaultBlockIsActive,
  getNextDefaultBlockTemperature,
  getNextDefaultLidIsActive,
  getNextDefaultLidTemperature,
  getNextDefaultLidOpen,
} from './getNextDefaultThermocyclerState'
export { stepFormToArgs } from './stepFormToArgs'
export type { FormError, FormWarning, FormWarningType }

type FormHelpers = {|
  getErrors?: mixed => Array<FormError>,
  getWarnings?: mixed => Array<FormWarning>,
|}

const stepFormHelperMap: { [StepType]: FormHelpers } = {
  mix: {
    getErrors: composeErrors(incompatibleLabware),
    getWarnings: composeWarnings(belowPipetteMinimumVolume),
  },
  pause: {
    getErrors: composeErrors(pauseForTimeOrUntilTold),
  },
  moveLiquid: {
    getErrors: composeErrors(
      incompatibleAspirateLabware,
      incompatibleDispenseLabware,
      wellRatioMoveLiquid
    ),
    getWarnings: composeWarnings(
      belowPipetteMinimumVolume,
      maxDispenseWellVolume,
      minDisposalVolume
    ),
  },
  magnet: {
    getErrors: composeErrors(
      magnetActionRequired,
      engageHeightRequired,
      moduleIdRequired,
      engageHeightRangeExceeded
    ),
  },
  temperature: {
    getErrors: composeErrors(targetTemperatureRequired, moduleIdRequired),
  },
  thermocycler: {
    getErrors: composeErrors(
      blockTemperatureRequired,
      lidTemperatureRequired,
      profileVolumeRequired,
      profileTargetLidTempRequired,
      blockTemperatureHoldRequired,
      lidTemperatureHoldRequired
    ),
  },
}

export const getFormErrors = (
  stepType: StepType,
  formData: mixed
): Array<FormError> => {
  const formErrorGetter =
    stepFormHelperMap[stepType] && stepFormHelperMap[stepType].getErrors
  const errors = formErrorGetter ? formErrorGetter(formData) : []
  return errors
}

export const getFormWarnings = (
  stepType: StepType,
  formData: mixed
): Array<FormWarning> => {
  const formWarningGetter =
    stepFormHelperMap[stepType] && stepFormHelperMap[stepType].getWarnings
  const warnings = formWarningGetter ? formWarningGetter(formData) : []
  return warnings
}
