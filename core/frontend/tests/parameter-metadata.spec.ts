import assert from 'node:assert/strict'
import test from 'node:test'

import {
  mergedMetadataForParameter,
  mergeParameterMetadata,
  normalizeComponentMetadata,
  selectArduPilotMetadataPath,
  updateComponentMetadataState,
} from '../src/types/autopilot/parameter-metadata'

const metadataPaths = [
  '/public/assets/ArduPilot-Parameter-Repository/AP_Periph-1.3/apm.pdef.json',
  '/public/assets/ArduPilot-Parameter-Repository/Sub-4.7/apm.pdef.json',
  '/public/assets/ArduPilot-Parameter-Repository/Sub-4.8/apm.pdef.json',
  '/public/assets/ArduPilot-Parameter-Repository/Sub-4.10/apm.pdef.json',
]

test('falls back to the newest metadata for the detected vehicle family', () => {
  assert.equal(
    selectArduPilotMetadataPath(metadataPaths, 'Sub', 0, 1),
    '/assets/ArduPilot-Parameter-Repository/Sub-4.10/apm.pdef.json',
  )
})

test('prefers an exact metadata match before the vehicle-family fallback', () => {
  assert.equal(
    selectArduPilotMetadataPath(metadataPaths, 'Sub', 4, 8),
    '/assets/ArduPilot-Parameter-Repository/Sub-4.8/apm.pdef.json',
  )
})

test('normalizes standard MAVLink parameter metadata', () => {
  const normalized = normalizeComponentMetadata({
    version: 3,
    parameters: [{
      name: 'SOURCE_TARGET',
      shortDesc: 'Selected target',
      longDesc: 'Runtime-discovered source',
      default: 0,
      min: 0,
      max: 16777215,
      increment: 1,
      readOnly: true,
      rebootRequired: true,
      values: [
        { value: 0, description: 'None' },
        { value: 65538, description: 'MAVLink 1.2' },
      ],
    }],
  })

  assert.deepEqual(normalized.SOURCE_TARGET, {
    Default: '0',
    Description: 'Runtime-discovered source',
    DisplayName: 'Selected target',
    Increment: '1',
    Range: { high: '16777215', low: '0' },
    ReadOnly: 'True',
    RebootRequired: 'True',
    Values: { 0: 'None', 65538: 'MAVLink 1.2' },
  })
})

test('component metadata overlays fields without discarding bundled definitions', () => {
  const bundled = {
    SOURCE_TARGET: {
      Description: 'Bundled description',
      DisplayName: 'Bundled title',
      Range: { low: '0', high: '100' },
      Units: 'id',
      Values: { 0: 'None', 1: 'Old target' },
    },
    UNCHANGED: { DisplayName: 'Unchanged' },
  }
  const component = normalizeComponentMetadata({
    version: 3,
    parameters: [{
      name: 'SOURCE_TARGET',
      max: 200,
      values: [{ value: 2, description: 'Detected target' }],
    }],
  })

  const merged = mergeParameterMetadata(bundled, component)
  assert.deepEqual(merged.SOURCE_TARGET, {
    Description: 'Bundled description',
    DisplayName: 'Bundled title',
    Range: { low: '0', high: '200' },
    Units: 'id',
    Values: { 2: 'Detected target' },
  })
  assert.deepEqual(merged.UNCHANGED, bundled.UNCHANGED)
  assert.notEqual(merged.UNCHANGED, bundled.UNCHANGED)
})

test('rejects malformed snapshots instead of partially replacing metadata', () => {
  assert.throws(
    () => normalizeComponentMetadata({ version: 3, parameters: [{ name: 'BROKEN', values: 'invalid' }] }),
    /values must be an array/,
  )
})

test('204 clears a prior runtime snapshot so bundled metadata becomes authoritative', () => {
  const loaded = updateComponentMetadataState(
    { metadata: {} },
    200,
    {
      version: 3,
      parameters: [{
        name: 'SOURCE_TARGET',
        values: [{ value: 42, description: 'Detected target' }],
      }],
    },
    '"1234"',
  )
  assert.equal(loaded.changed, true)
  assert.deepEqual(loaded.metadata.SOURCE_TARGET.Values, { 42: 'Detected target' })

  const cleared = updateComponentMetadataState(loaded, 204)
  assert.deepEqual(cleared, { metadata: {}, etag: undefined, changed: true })

  const bundled = { SOURCE_TARGET: { Values: { 0: 'None' } } }
  assert.deepEqual(mergeParameterMetadata(bundled, cleared.metadata), bundled)
})

test('accepts integer metadata versions 3 and newer and rejects older or fractional versions', () => {
  assert.deepEqual(normalizeComponentMetadata({ version: 3, parameters: [] }), {})
  assert.deepEqual(normalizeComponentMetadata({ version: 4, parameters: [] }), {})
  assert.throws(() => normalizeComponentMetadata({ version: 2, parameters: [] }), /document is invalid/)
  assert.throws(() => normalizeComponentMetadata({ version: 3.5, parameters: [] }), /document is invalid/)
})

test('component templates overlay only matching loaded parameter names', () => {
  const bundled = {
    FOO1_BAR: { Description: 'First bundled', Units: 'm' },
    FOO2_BAR: { Description: 'Second bundled', Units: 'm' },
    OTHER: { Description: 'Unrelated' },
  }
  const component = {
    'FOO{n}_BAR': { DisplayName: 'Detected source', Values: { 7: 'Target seven' } },
  }

  assert.deepEqual(mergedMetadataForParameter(bundled, component, 'FOO1_BAR'), {
    Description: 'First bundled',
    DisplayName: 'Detected source',
    Units: 'm',
    Values: { 7: 'Target seven' },
  })
  assert.deepEqual(mergedMetadataForParameter(bundled, component, 'FOO2_BAR'), {
    Description: 'Second bundled',
    DisplayName: 'Detected source',
    Units: 'm',
    Values: { 7: 'Target seven' },
  })
  assert.deepEqual(mergedMetadataForParameter(bundled, component, 'OTHER'), bundled.OTHER)
  assert.equal(mergedMetadataForParameter(bundled, component, 'FOOX_BAR'), undefined)
})
