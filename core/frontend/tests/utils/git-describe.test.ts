import '@/cosmos'

import { describe, expect, it } from 'bun:test'

import { convertGitDescribeToTag, convertGitDescribeToUrl, isCloudTrayMenuVisible } from '@/utils/helper_functions'

const PROJECT = 'https://github.com/bluerobotics/BlueOS'

describe('GIT_DESCRIBE_TAGS', () => {
  it('links a tag build to its release', () => {
    expect(convertGitDescribeToTag('1.4.0-0-gabcdef12')).toBe('1.4.0')
    expect(convertGitDescribeToUrl('1.4.0-0-gabcdef12')).toBe(`${PROJECT}/releases/tag/1.4.0`)
  })

  it('reads a pre-release tag', () => {
    expect(convertGitDescribeToTag('1.5.0-beta.3-0-gabcdef12')).toBe('1.5.0-beta.3')
  })

  it('links commits after a tag to that commit', () => {
    expect(convertGitDescribeToTag('1.4.0-10-gabcdef12')).toBeUndefined()
    expect(convertGitDescribeToUrl('1.4.0-10-gabcdef12')).toBe(`${PROJECT}/tree/abcdef12`)
  })

  it('does not take a two-digit distance for a tag build', () => {
    expect(convertGitDescribeToTag('1.4.0-12-gabcdef12')).toBeUndefined()
  })

  it('links an empty description to the project', () => {
    expect(convertGitDescribeToTag('')).toBeUndefined()
    expect(convertGitDescribeToUrl('')).toBe(PROJECT)
  })
})

describe('cloud tray menu', () => {
  it('is hidden on a stable release', () => {
    expect(isCloudTrayMenuVisible('1.4.0-0-gabcdef12')).toBe(false)
  })

  it('is shown on a beta release', () => {
    expect(isCloudTrayMenuVisible('1.5.0-beta.3-0-gabcdef12')).toBe(true)
  })

  it('is shown on a commit after a stable tag', () => {
    expect(isCloudTrayMenuVisible('1.4.0-5-gabcdef12')).toBe(true)
  })

  it('is hidden while the version is unknown', () => {
    expect(isCloudTrayMenuVisible('')).toBe(false)
  })
})
