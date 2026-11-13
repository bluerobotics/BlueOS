import use_nixos_updates from '@/utils/updates_backend'
import * as VersionChooserDocker from '@/utils/version_chooser'
import * as VersionChooserNixos from '@/utils/version_chooser_nixos'

/** Restarting the core means a different endpoint depending on the backend. */
const version_chooser_api = use_nixos_updates ? VersionChooserNixos : VersionChooserDocker

const restartCore = version_chooser_api.restartCore

export { restartCore }
