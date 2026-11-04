const DOCKER_HUB_REGISTRY = 'docker.io'

function splitTag(image: string): [string, string] {
  const without_digest = image.split('@')[0]
  const last_slash = without_digest.lastIndexOf('/')
  const last_colon = without_digest.lastIndexOf(':')

  if (last_colon > last_slash) {
    return [without_digest.slice(0, last_colon), without_digest.slice(last_colon + 1)]
  }
  return [without_digest, 'latest']
}

/**
 * The `library/` namespace is implied only on Docker Hub, so it is added for
 * that registry alone: `alpine` and `docker.io/library/alpine` are the same
 * image, while `quay.io/foo` is a single-component path that already is the
 * full repository name.
 */
function normalizeRepository(repository: string): string {
  const parts = repository.split('/')
  const first = parts[0]
  const has_host = parts.length > 1 && (first.includes('.') || first.includes(':') || first === 'localhost')

  const host = has_host ? (parts.shift() as string) : DOCKER_HUB_REGISTRY
  if (parts.length === 1 && host === DOCKER_HUB_REGISTRY) {
    parts.unshift('library')
  }
  return `${host}/${parts.join('/')}`
}

/**
 * Docker reports a container's image exactly as it was requested, so an
 * extension declared as `bluerobotics/blueos-ping-viewer-next` and its running
 * container both carry that unqualified name. Podman instead reports the
 * fully-qualified reference (`docker.io/bluerobotics/...`), which makes a
 * strict comparison report every installed extension as not running.
 */
export default function imageNameMatches(running: string, expected: string): boolean {
  const [running_repository, running_tag] = splitTag(running)
  const [expected_repository, expected_tag] = splitTag(expected)

  return (
    normalizeRepository(running_repository) === normalizeRepository(expected_repository) &&
    running_tag === expected_tag
  )
}
