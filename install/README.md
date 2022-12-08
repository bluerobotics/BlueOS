# Installation directory

This folder contains all necessary files for configuration of the host computer and installation of blueos-docker.

To use it, just run the installation script in your terminal **as root**, like so:

```bash
sudo su -c 'curl -fsSL https://raw.githubusercontent.com/bluerobotics/blueos-docker/master/install/install.sh | bash'
```

# Using different versions or custom builds
To use a different remote or version, you can se the following environment variables:
- `REMOTE`: Where the files are, E.g: https://raw.githubusercontent.com/patrickelectric/blueos-docker
- `VERSION`: Branch (If using GitHub) or folder (If using HTTP server) to be used.

Remember that to do that, you need to set the environment variables as root:
```sh
sudo su
# You can also change the install URL to use a different source for files
curl -fsSL https://raw.githubusercontent.com/patrickelectric/blueos-docker/example-version/install/install.sh | export REMOTE=https://raw.githubusercontent.com/patrickelectric/blueos-docker export VERSION=example-version bash
```