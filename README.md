# BlueOS

[![Test, Build and Deploy Images](https://github.com/bluerobotics/BlueOS-docker/actions/workflows/test-and-deploy.yml/badge.svg)](https://github.com/bluerobotics/BlueOS-docker/actions/workflows/test-and-deploy.yml)
![Downloads](https://img.shields.io/github/downloads/bluerobotics/blueos-docker/total?label=Downloads)

[![Latest Stable](https://img.shields.io/github/v/release/bluerobotics/blueos-docker.svg?label=Latest%20Stable)
![Date](https://img.shields.io/github/release-date/bluerobotics/blueos-docker?label=Date)](https://github.com/bluerobotics/blueos-docker/releases/latest)

[![Latest Beta](https://img.shields.io/github/v/tag/bluerobotics/blueos-docker.svg?label=Latest%20Beta)
![Date](https://img.shields.io/github/release-date-pre/bluerobotics/blueos-docker?label=Date)](https://github.com/bluerobotics/BlueOS-docker/releases)


[![Docker](https://img.shields.io/docker/v/bluerobotics/blueos-core?label=Docker&style=flat)
![Pulls](https://img.shields.io/docker/pulls/bluerobotics/blueos-core?label=Pulls)
![Size](https://img.shields.io/docker/image-size/bluerobotics/blueos-core?label=Size)](https://hub.docker.com/r/bluerobotics/blueos-core/tags)

BlueOS is a modular, robust, and efficient platform for managing a vehicle or robot from its onboard computer. It is the evolution of the Companion project that initially aimed to route a vehicle's video stream and communications to the surface computer. Recognizing the need for a more sophisticated and scalable system, BlueOS was created from the ground up, embracing modularity to ensure portability, robust updating, and extensibility.

<p align="center">
  <a href="doc/dashboard.png">
    <img src="doc/dashboard.png" width="75%">
  </a>
</p>

## Quick Links ⚡

- [Official documentation](https://docs.bluerobotics.com/ardusub-zola/software/onboard/).
- For custom installations see the [install directory](https://github.com/bluerobotics/BlueOS-docker/blob/master/install).

## Principles and Goals 📖

The development of BlueOS is driven by the following core principles:

* An interface that is **simple by default but powerful when needed** - the user has the power to change anything they desire and customize the full experience
* **Designed to focus on what matters**, improving user access to information and controls with a human-friendly UI and UX
* **Make complex tasks simpler** and improve ease of use by reusing design patterns from other applications (based on the [material UI guidelines](https://material.io/design/guidelines-overview))
* **Advanced error handling and detection**, making any problems clear to the user and developers, along with how to fix them
* **Simplify development**, providing full access to our services API and modular development model
* **Portable and flexible**, you should be able to run on a Raspberry Pi 3/4 or any SBC with Linux operating system, contributions are welcomed
* **Highly functional with low CPU usage**, the entire system is built to run efficiently
* **Developed on solid foundations**, critical parts or intensive workforce services are designed using the most advanced languages and features available for stability

The design, organization, and future releases of BlueOS are aligned with these principles, striving to provide an optimized and enriched user experience.

## Release Types ✨

BlueOS is available in three release types:

- **Stable:** Officially tested and validated versions with long-term support. Recommended for most users.
- **Beta:** Quick-passed rolling releases with new features, bug fixes, and improvements.
- **Master:** Rapidly-passed bleeding-edge development releases. These are the very latest features that may not have been tested yet.

## Vehicle Support

BlueOS has been designed with a focus on vehicle and to be platform agnosticism. Our aim is to facilitate broad compatibility across a wide spectrum of applications. Currently, BlueOS officially supports the following vehicle types:

### **Boats (ArduRover)**

ArduRover is an open-source, unmanned boat platform. Whether you are commanding a leisure boat or a research vessel, BlueOS's compatibility with ArduRover ensures that you can navigate the waters smoothly 🌊.

![](doc/blueboat.png)

### **Submarines (ArduSub)**

ArduSub is the go-to control system for remotely operated underwater vehicles (ROVs) 🐟. BlueOS offers seamless integration with ArduSub, enabling efficient management and operation of underwater vehicles. Right now it provides support for BlueROV2 out of the box.

![](doc/bluerov.png)

### **Generic (ArduPilot / PX4)**

For a wide array of unmanned vehicles, whether terrestrial, aerial, or marine, BlueOS provides support for the generic ArduPilot and PX4 autopilots. This extends the range of vehicles that can be managed using our system, from drones to autonomous cars and more.

**Note:** Specific vehicle configuration may be necessary to ensure optimal performance with BlueOS.

## Supported Architectures 👨🏻‍💻

BlueOS is designed to perform optimally across a wide range of systems. In our latest releases, we officially support the following architectures:

- **amd64:** This is the architecture used by most desktop and laptop computers. A typical example is any modern PC running a 64-bit version of Linux.

- **armv8/arm64:** This is used by more recent, high-performance devices. You can run BlueOS on a Raspberry Pi 4 or in a computer with Apple Silicon.

- **armv7:** This is a common architecture for embedded devices. Raspberry Pi models up to and including the Raspberry Pi 3.

Right now we officially support the Raspberry Pi 3 and Raspberry Pi 4, but the system should just work on all listed architectures with the correct docker bind.
