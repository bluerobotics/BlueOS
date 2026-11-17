{
  config,
  lib,
  ...
}:
let
  cfg = config.services.blueos;

  gitDescribe = cfg.gitDescribe;

  release = {
    inherit (cfg) version revision channel;
  };
in
{
  config = lib.mkIf cfg.enable {
    system.nixos.label = lib.mkForce "blueos-${gitDescribe}-${config.system.nixos.version}";

    system.configurationRevision = lib.mkDefault cfg.revision;

    environment.etc."blueos/release.json".text = builtins.toJSON release;

    environment.variables.GIT_DESCRIBE_TAGS = lib.mkDefault gitDescribe;
  };
}
