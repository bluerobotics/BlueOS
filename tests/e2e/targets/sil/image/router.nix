{ lib, pkgs, ... }:
let
  wan = "ens3";
  # Proxies port from the router netns, where the qemu hostfwd lands, to the VM
  forward = port: {
    sockets."router-${toString port}" = {
      wantedBy = [ "container@router.service" ];
      after = [ "container@router.service" ];
      bindsTo = [ "container@router.service" ];
      # Otherwise it is ordered before the container, through sockets.target
      unitConfig.DefaultDependencies = false;
      socketConfig = {
        ListenStream = port;
        NetworkNamespacePath = "/run/netns/router";
      };
    };
    services."router-${toString port}".serviceConfig.ExecStart =
      "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd 127.0.0.1:${toString port}";
  };
in
{
  # The router, like the one a Pi is wired to. It holds the qemu nic, hidden from BlueOS, and NATs its switch (br0) to
  # the internet. Two cables are plugged into the switch: eth0 to the vehicle, and client to a simulated PC.
  containers.router = {
    autoStart = true;
    privateNetwork = true;
    interfaces = [ wan ];
    extraVeths.eth0 = { };
    extraVeths.client = { };
    config = {
      system.stateVersion = "26.05";
      environment.systemPackages = [ pkgs.iptables ];
      networking.interfaces.${wan}.ipv4.addresses = [ { address = "10.0.2.15"; prefixLength = 24; } ];
      networking.bridges.br0.interfaces = [ "eth0" "client" ];
      networking.interfaces.br0.ipv4.addresses = [ { address = "192.168.1.1"; prefixLength = 24; } ];
      networking.defaultGateway = "10.0.2.2";
      networking.firewall.enable = false;
      networking.nat = {
        enable = true;
        externalInterface = wan;
        internalInterfaces = [ "br0" ];
      };
      # Only DHCP, with the qemu dns, so the tests can stop it without cutting dns
      services.dnsmasq = {
        enable = true;
        settings = {
          port = 0;
          interface = "br0";
          dhcp-range = "192.168.1.100,192.168.1.200,12h";
          dhcp-option = "option:dns-server,10.0.2.3";
        };
      };
    };
  };

  networking.networkmanager.unmanaged = [ "interface-name:${wan}" ];
  networking.nameservers = [ "10.0.2.3" ];
  environment.systemPackages = [ pkgs.dhcpcd ];

  systemd = lib.mkMerge [
    # Router netns
    {
      services."container@router".postStart = lib.mkAfter ''
        ${pkgs.iproute2}/bin/ip netns delete router 2> /dev/null || true
        ${pkgs.iproute2}/bin/ip netns attach router "$(${pkgs.systemd}/bin/machinectl show router -p Leader --value)"
      '';
    }
    (forward 22)
    (forward 80)
    # Client PC netns
    {
      services."container@router".postStart = lib.mkAfter ''
        ${pkgs.iproute2}/bin/ip netns add client
        ${pkgs.iproute2}/bin/ip link set client netns client
        ${pkgs.iproute2}/bin/ip -n client link set client up
      '';
    }
  ];
}
