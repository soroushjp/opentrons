'use strict'

module.exports = {
  setupFilesAfterEnv: [
    '<rootDir>/scripts/setup-enzyme.js',
    '<rootDir>/scripts/setup-global-mocks.js',
  ],
  globals: {
    __webpack_public_path__: '/',
  },
  moduleNameMapper: {
    '\\.(css)$': 'identity-obj-proxy',
  },
  transform: {
    '^.+\\.(js|ts|tsx)$': 'babel-jest',
    '\\.(jpg|png|gif|svg|woff|woff2|webm)$':
      '@opentrons/components/src/__mocks__/file.js',
  },
  modulePathIgnorePatterns: [
    '/shared-data/python/.*',
    '/api/.*',
    '/robot-server/.*',
    '/update-server/.*',
  ],
  transformIgnorePatterns: ['/node_modules/(?!@opentrons/)'],
  collectCoverageFrom: [
    'app/src/**/*.js',
    'app-shell/src/**/*.js',
    'components/src/**/*.js',
    'discovery-client/src/**/*.ts',
    'labware-library/src/**/*.js',
    'protocol-designer/src/**/*.js',
    'shared-data/js/**/*.js',
    '!**/__mocks__/**',
    '!**/__tests__/**',
    '!**/__fixtures__/**',
    '!**/__utils__/**',
    '!**/test/**',
    '!**/scripts/**',
  ],
  testPathIgnorePatterns: [
    'cypress/',
    '/node_modules/',
    '.*.d.ts',
    '.*.flow.js',
  ],
  coverageReporters: ['lcov', 'text-summary'],
  snapshotSerializers: ['enzyme-to-json/serializer'],
  watchPathIgnorePatterns: ['/node_modules/'],
}
