# BlueOS

[![Test, Build and Deploy Images](https://github.com/bluerobotics/BlueOS/actions/workflows/test-and-deploy.yml/badge.svg)](https://github.com/bluerobotics/BlueOS/actions/workflows/test-and-deploy.yml)
![Downloads](https://img.shields.io/github/downloads/bluerobotics/blueos/total?label=Downloads)
[![Discord](https://img.shields.io/discord/1135646343776456765?label=Discord)](https://discord.gg/y9JNPDMsFv)

[![Latest Stable](https://img.shields.io/github/v/release/bluerobotics/blueos.svg?label=Latest%20Stable)
![Date](https://img.shields.io/github/release-date/bluerobotics/blueos?label=Date)](https://github.com/bluerobotics/blueos/releases/latest)

[![Latest Beta](https://img.shields.io/github/v/tag/bluerobotics/blueos.svg?label=Latest%20Beta)
![Date](https://img.shields.io/github/release-date-pre/bluerobotics/blueos?label=Date)](https://github.com/bluerobotics/BlueOS/releases)


[![Docker](https://img.shields.io/docker/v/bluerobotics/blueos-core?label=Docker&style=flat)
![Pulls](https://img.shields.io/docker/pulls/bluerobotics/blueos-core?label=Pulls)
![Size](https://img.shields.io/docker/image-size/bluerobotics/blueos-core?label=Size)](https://hub.docker.com/r/bluerobotics/blueos-core/tags)

BlueOS is a modular, robust, and efficient platform for managing a vehicle or robot from its [onboard computer](https://blueos.cloud/docs/hardware/required/onboard-computer/). It is the evolution of the Companion project, which aimed to route a vehicle's video stream and communications to its [control station computer](https://blueos.cloud/docs/hardware/required/control-computer/). Recognizing the need for a more sophisticated and scalable system, BlueOS was created from the ground up, embracing modularity to ensure portability, robust updating, and extensibility.

<p align="center">
  <a href="doc/dashboard.png">
    <img src="doc/dashboard.png" width="75%">
  </a>
</p>

## Quick Links ⚡

- [Official documentation](https://blueos.cloud/docs/)
- [Installation](https://blueos.cloud/docs/stable/usage/installation/)
- [Development documentation](https://blueos.cloud/docs/latest/development/overview/)
- [Contributions](https://blueos.cloud/docs/latest/development/core/#contributions)
- [Code of Conduct](./CoC.md)
- [Registered Extensions](https://docs.bluerobotics.com/BlueOS-Extensions-Repository)
- [Custom installation](#custom-installation)

## Principles and Goals 📖

The development of BlueOS is driven by the following core principles:

* An interface that is **simple by default but powerful when needed** - the user has the power to change anything they desire and customize the full experience
* **Designed to focus on what matters**, improving user access to information and controls with a human-friendly UI and UX
* **Make complex tasks simpler** and improve ease of use by reusing design patterns from other applications (based on the [material UI guidelines](https://material.io/design/guidelines-overview))
* **Advanced error handling and detection**, making any problems clear to the user and developers, along with how to fix them
* **Simplify development**, providing full access to our [services API](https://blueos.cloud/docs/blueos/1.1/development/core/#services) and [modular development model](https://blueos.cloud/docs/blueos/1.1/development/overview/)
* **Portable and flexible**, you should be able to run on a Raspberry Pi 3/4/5 or any SBC with Linux operating system, contributions are welcomed
* **Highly functional with low CPU usage**, the entire system is built to run efficiently
* **Developed on solid foundations**, critical parts or intensive workforce services are designed using the most advanced languages and features available for stability

The design, organization, and future releases of BlueOS are aligned with these principles, striving to provide an optimized and enriched user experience.

## Release Types ✨

BlueOS is available in three release types:

- **Stable:** Officially tested and validated versions with long-term support. Recommended for most users.
- **Beta:** Lightly tested rolling releases with new features, bug fixes, and improvements.
- **Master:** Bleeding-edge development releases with almost daily changes. These are the very latest features that may not have been tested yet.

## Vehicle Support 🛸

BlueOS has been designed with a focus on vehicle and platform agnosticism. Our aim is to facilitate broad compatibility across a wide spectrum of applications. Currently, BlueOS officially supports the following vehicle types:

### **Boats (ArduRover)**

ArduRover is an open-source, uncrewed boat platform. Whether you are commanding a leisure boat or a research vessel, BlueOS's compatibility with ArduRover ensures that you can navigate the waters smoothly 🌊.

[BlueBoat](https://bluerobotics.com/store/blueboat/blueboat/) is supported by default.

![](doc/blueboat.png)

### **Submarines (ArduSub)**

ArduSub is the go-to control system for remotely operated underwater vehicles (ROVs) 🐟. BlueOS offers seamless integration with ArduSub, enabling efficient management and operation of underwater vehicles.

[BlueROV2](https://bluerobotics.com/store/rov/bluerov2/) is supported out of the box.

![](doc/bluerov.png)

### **Generic (ArduPilot / PX4)**

BlueOS provides generic support for a wide variety of terrestrial, aerial, and marine uncrewed vehicles that use ArduPilot and PX4 autopilots. This extends the range of vehicles that can be managed using our system, from drones to autonomous cars and more.

>**Note:** Specific vehicle configuration may be necessary to ensure optimal performance with BlueOS.

## Custom installation

### Raspberry Pi and hardware preparation

For installations that need hardware configuration and preparation of the operating system, it´s highly recommended to use [the installation script](https://github.com/bluerobotics/BlueOS/blob/master/install) and customize it as necessary to perform the necessary changes for your system.

### Running BlueOS

It's highly recommended to have debian, debian based (like ubuntu) or any linux distribution with similar services and tools to run BlueOS. This is necessary since BlueOS use specific components on the host computer to do software configuration and take control of the system.

#### Running via Docker Compose (`docker compose`)

1. Clone the repository with git
      - `git clone --depth=1 --recurse-submodules --shallow-submodules https://github.com/bluerobotics/blueos`
2. Modify [core/compose/compose.yml](core/compose/compose.yml) example file.
      - `BLUEOS_DISABLE_SERVICES`: Comment or remove this line if you want BlueOS to have full access of the system, including wifi and ethernet configuration.
      - `BLUEOS_DISABLE_MEMORY_LIMIT`: Comment or remove this line if running in a system with 4GB of RAM memory or less.
      - `BLUEOS_DISABLE_STARTUP_UPDATE`: This environment variable is necessary, "startup update" procedure is only required when bootstrap is running to manage the system (not the case when using docker compose).
      - `SSH_USER`: Uncomment and update the value for the SSH user, required for BlueOS to run commands and access the host computer if necessary.
      - `SSH_PASSWORD`: Uncomment and update the value for the SSH user password.
3. Run docker compose
      - ```bash
        cd core/compose/ && docker compose pull && cd - # Ensure that docker is up-to-date
        docker compose -f core/compose/compose.yml up
        ```

In the end, your docker compose file should look like this

```compose
version: "3.7"
services:
  blueos-core:
    container_name: blueos-core
    image: bluerobotics/blueos-core:master
    privileged: true
    network_mode: host
    pid: host
    restart: unless-stopped
    environment:
      - BLUEOS_DISABLE_MEMORY_LIMIT=true
      - BLUEOS_DISABLE_STARTUP_UPDATE=true
      - SSH_USER=pi
      - SSH_PASSWORD=raspberry
    volumes:
      - ./workspace/.config:/root/.config
      - ./workspace/etc/blueos:/etc/blueos
      - ./workspace/tmp/wpa_playground:/tmp/wpa_playground
      - ./workspace/usr/blueos/bin:/usr/blueos/bin
      - ./workspace/usr/blueos/extensions:/usr/blueos/extensions
      - ./workspace/usr/blueos/userdata:/usr/blueos/userdata
      - ./workspace/var/logs/blueos:/var/logs/blueos
      - /dev:/dev
      - /etc/dhcpcd.conf:/etc/dhcpcd.conf
      - /etc/machine-id:/etc/machine-id:ro
      - /etc/resolv.conf.host:/etc/resolv.conf.host:ro
      - /run/udev:/run/udev:ro
      - /sys:/sys
      - /var/run/dbus:/var/run/dbus
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/run/wpa_supplicant:/var/run/wpa_supplicant
      - /home/patrick/.ssh:/home/pi/.ssh
```

The system should be accessible now via `0.0.0.0:80` or via the network using the IP address of the device.


#### Running via Docker (`docker run`)

You can update the script to follow your board configuration. Here, we are creating temporary folders for the binds, but it's highly recommended to create a workspace environment where you can set the binds to be persistent.

```bash
# Prepare workspace
mkdir -p /tmp/workspace/var/logs/blueos
mkdir -p /tmp/workspace/.config
mkdir -p /tmp/workspace/tmp/wpa_playground
mkdir -p /tmp/workspace/etc/blueos
mkdir -p /tmp/workspace/usr/blueos/{bin,extensions,userdata}

# Docker command
docker run --privileged --network=host --pid=host --name=blueos-core \
  --mount type=bind,source=/dev/,target=/dev/,readonly=false \  # Required for hardware access
  --mount type=bind,source=/sys/,target=/sys/,readonly=false \  # Required for system access
  --mount type=bind,source=/var/run/wpa_supplicant,target=/var/run/wpa_supplicant,readonly=false \ # Required for wifi control
  --mount type=bind,source=/tmp/workspace/tmp/wpa_playground,target=/tmp/wpa_playground,readonly=false \ # Required for wifi control
  --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock,readonly=false \ # Required for docker control
  --mount type=bind,source=/tmp/workspace/var/logs/blueos,target=/var/logs/blueos,readonly=false \ # Required for BlueOS log files
  --mount type=bind,source=/run/udev,target=/run/udev,readonly=true \ # Required for hardware information
  --mount type=bind,source=$HOME/.ssh,target=/home/pi/.ssh,readonly=false \ # Required for host computer access from BlueOS
  --mount type=bind,source=/tmp/workspace/etc/blueos,target=/etc/blueos,readonly=false \ # Required for bash history and other files
  --mount type=bind,source=/etc/machine-id,target=/etc/machine-id,readonly=true \ # Required for hardware / system information
  --mount type=bind,source=/etc/dhcpcd.conf,target=/etc/dhcpcd.conf,readonly=false \ # Required for ethernet control
  --mount type=bind,source=/tmp/workspace/usr/blueos/userdata,target=/usr/blueos/userdata,readonly=false \ # Required for extension data
  --mount type=bind,source=/tmp/workspace/usr/blueos/extensions,target=/usr/blueos/extensions,readonly=false \ # Required for extension data
  --mount type=bind,source=/tmp/workspace/usr/blueos/bin,target=/usr/blueos/bin,readonly=false \ # Required for custom binaries
  --mount type=bind,source=/etc/resolv.conf.host,target=/etc/resolv.conf.host,readonly=true \ # Required for ethernet configuration
  --mount type=bind,source=/var/run/dbus,target=/var/run/dbus,readonly=false \ # Required for wifi and others services access
  --mount type=bind,source=/tmp/workspace/.config,target=/root/.config,readonly=false \ # Required for persistent BlueOS configuration
  -e BLUEOS_DISABLE_MEMORY_LIMIT=true \
  -e BLUEOS_DISABLE_STARTUP_UPDATE=true \
  -e SSH_USER=pi \
  -e SSH_PASSWORD=raspberry \
  bluerobotics/blueos-core:master
```

After running BlueOS like this, the system should be accessible now via `0.0.0.0:80` or via the network using the IP address of the device.

## Supported Architectures 👨🏻‍💻

BlueOS is designed to perform optimally across a wide range of systems. Our latest releases are automatically built for the following architectures:

- **armv7:** This is a common architecture for embedded devices. Covers Raspberry Pi models up to and including the **Raspberry Pi 3** and **Raspberry Pi 4**.

- **armv8/arm64:** This is used by more recent, high-performance devices. You can run BlueOS on a Raspberry Pi 4 (not recommended, use the armv7 image for a better experience), **Raspberry Pi 5**, or in a computer with Apple Silicon.

- **amd64:** This is the architecture used by most desktop and laptop computers. A typical example is any modern PC running a 64-bit version of Linux. **Not fully supported.**

Right now we officially support the Raspberry Pi 3, 4 and 5, but the system should "just work" on all listed architectures with the correct docker binds.

## Development Environment

Docker based development environment is available for via the [`core/compose/compose.yml`](core/compose/compose.yml) docker compose file. This will start a development environment with all the required services as well as mount all of the needed directories in this repository for development.

```bash
cd core/compose/ && docker compose pull && cd - # Ensure that docker is up-to-date
docker compose -f core/compose/compose.yml up
```

When restarting the development environment you may need to remove the volumes to ensure that the development environment is clean.

```bash
docker compose -f core/compose/compose.yml down
```

### Known issues

Docker compose is not fully compatible with a standard installation of BlueOS.

- MDNS may not work
    - Access should be done via `0.0.0.0:80`
- Some services are disabled
    - cable_guy, wifi, commander
    - This may result in errors on the frontend
