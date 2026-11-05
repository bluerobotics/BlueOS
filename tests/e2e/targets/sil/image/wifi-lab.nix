{ pkgs, ... }:
let
  # Radios the tests use as access points and scanners, wlan0 is BlueOS' own on top of these
  labRadios = 5;
in
{
  # Enable the mac80211_hwsim module to simulate wifi radios
  boot.kernelModules = [ "mac80211_hwsim" ];
  boot.extraModprobeConfig = ''
    options mac80211_hwsim radios=${toString (labRadios + 1)} channels=2
    options cfg80211 ieee80211_regdom=US
  '';
  hardware.wirelessRegulatoryDatabase = true;
  environment.systemPackages = with pkgs; [ dnsmasq hostapd iw ];

  # Hides the radios that simulate the outside world from BlueOS, so it only sees its own wlan0
  systemd.services.wifi-lab = {
    wantedBy = [ "multi-user.target" ];
    after = [ "systemd-modules-load.service" ];
    before = [ "NetworkManager.service" "docker.service" ];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
    };
    path = with pkgs; [ iproute2 iw ];
    script = ''
      ip netns add lab
      ip netns exec lab ip link set lo up
      blueos=$(cat /sys/class/net/wlan0/phy80211/name)
      for phy in $(ls /sys/class/ieee80211); do
        [ "$phy" = "$blueos" ] || iw phy "$phy" set netns name lab
      done
    '';
  };
}
