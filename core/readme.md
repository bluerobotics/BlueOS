# Blueos Core Container

## Build:

1. [Install docker](https://docs.docker.com/get-docker/).
2. Setup buildx:
```
docker buildx create --name multiarch --driver docker-container --use
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```
3. Build this container:
```
docker buildx build --build-arg VUE_APP_GIT_DESCRIBE=$(git describe --long --always --dirty --all) --build-arg GIT_DESCRIBE_TAGS=$(git describe --tags --long)   --platform linux/arm/v7 . -t YOURDOCKERHUB/blueos-core:YOURTAG --output type=registry
```