/**
 * Which update backend this frontend was built for.
 *
 * A NixOS build replaces the container version chooser with one backed by system
 * generations. Both implementations are bundled and this only picks between
 * them, so a change to the default does not require touching either one.
 */
const use_nixos_updates = import.meta.env.VITE_BLUEOS_UPDATES === 'nixos'

export default use_nixos_updates
