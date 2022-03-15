Bootstrap is responsible for setting things up for the first run of BlueOS and applying updates.

To build the docker image:

```bash
cd bootstrap
docker build . --tag bluerobotics/bootstrap:master
```


Usage:

Everytime it is launched, it will load the startup settings, wait until the core container is not running, and re-create and re-launch it.

```bash
docker run -it -v /var/run/docker.sock:/var/run/docker.sock -v /config:/config  bluerobotics/bootstrap:master
```

This will automatically populate /config if there is no valid config file in there, fetch if necessary, and then launch BlueOS.