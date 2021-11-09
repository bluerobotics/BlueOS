# How to run:

1. Install pimod
1. Run pimod using the current file as source

# FAQ

## Docker fails to run with a cgroup problem
It may need to uncomment the cgroup_controllers configuration on `qemu.conf` for cgroup bind

## Docker fails to connect with docker.com API
It may be necessary to set `resolv.conf` on qemu or bind it with host