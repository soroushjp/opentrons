// @flow

import {
  MAGDECK,
  MAGNETIC_MODULE_V1,
  MODULE_MODELS,
  MODULE_TYPES,
  TEMPDECK,
  TEMPERATURE_MODULE_V1,
  THERMOCYCLER,
  THERMOCYCLER_MODULE_V1,
} from '../constants'
import {
  getModuleDef2,
  getModuleDisplayName,
  getModuleType,
  normalizeModuleModel,
} from '../modules'

describe('all valid models work', () => {
  MODULE_MODELS.forEach(model => {
    const loadedDef = getModuleDef2(model)
    it('ensure valid models load', () => {
      expect(loadedDef).not.toBeNull()
      expect(loadedDef?.model).toEqual(model)
    })
    it('valid models have valid module types', () => {
      expect(getModuleType(model)).toEqual(loadedDef.moduleType)
      expect(MODULE_TYPES).toContain(getModuleType(model))
    })
    it('valid modules have display names that match the def', () => {
      expect(getModuleDisplayName(model)).toEqual(loadedDef.displayName)
    })
  })
})

describe('legacy models work too', () => {
  const legacyEquivs = [
    [TEMPDECK, TEMPERATURE_MODULE_V1],
    [MAGDECK, MAGNETIC_MODULE_V1],
    [THERMOCYCLER, THERMOCYCLER_MODULE_V1],
  ]
  legacyEquivs.forEach(([legacy, modern]) => {
    const fromLegacy = normalizeModuleModel(legacy)
    expect(fromLegacy).toEqual(modern)
  })
})
