import threading
import time
from typing import Optional, List, Dict, Any
import docker
from docker.models.containers import Container


class StatusFetcher(threading.Thread):
    """
    Class responsible for creating threads for tracking stats of each docker
    container in use
    """

    client = docker.from_env()
    container: Container
    status: Dict[str, Any] = {}  # holds the status for each container
    previous_system_cpu: float = 0
    previous_docker_cpu: float = 0
    previous_tx: float = 0
    previous_rx: float = 0

    def __init__(self, container: Container):
        threading.Thread.__init__(self)
        print(f"created StatusFetcher thread for {container.image}")
        self.container = container
        self.start()

    def run(self) -> None:
        """
        Iterates through the container.stats stream,
        saving the data to a local shared dict.
        Automatically ends when the container dies.
        """

        for stats in self.container.stats(stream=True, decode=True):
            try:
                current_docker_cpu = stats["cpu_stats"]["cpu_usage"]["total_usage"]
                current_system_cpu = stats["cpu_stats"]["system_cpu_usage"]
                docker_delta = current_docker_cpu - self.previous_docker_cpu
                system_delta = current_system_cpu - self.previous_system_cpu
                self.previous_system_cpu = current_system_cpu
                self.previous_docker_cpu = current_docker_cpu
                self.status = {
                    "image": self.container.image.tags,
                    "cpu_usage": 100.0 * docker_delta / system_delta,
                    "memory_usage": stats["memory_stats"]["usage"] / 1024 / 1024,
                }
                if "networks" in stats:
                    new_tx = stats["networks"]["eth0"]["tx_bytes"] / 1024
                    new_rx = stats["networks"]["eth0"]["rx_bytes"] / 1024
                    self.status["network_tx"] = new_tx - self.previous_tx
                    self.status["network_rx"] = new_rx - self.previous_rx
                    self.previous_rx = new_rx
                    self.previous_tx = new_tx
            except KeyError as error:
                print("Unable to acces data for container!", self.container, error)
                continue
        print(f"StatusFetcher for {self.container} is done")


class Service:
    """Abstraction around docker containers, used to create, manage, and mantain stats for the services"""

    image: str  # Docker image (for example bluerobotics/core)
    registry: str = "http://hub.docker.com"
    version: str  # (1.0.0-alpha.1, latest, master, stable)
    statusfetcher: Optional[StatusFetcher] = None
    container: Optional[Container] = None
    config: Dict[str, Any]
    enabled: bool
    client = docker.from_env()
    starts: int = 0
    stored_logs: str = ""
    available_tags: List[str]

    def __init__(self, config: Dict[str, Any]) -> None:
        self.available_tags: List[str] = []
        self.last_tag_update: float = 0
        self.image = config["image"]
        self.version = config["tag"]
        self.enabled = config["enabled"]
        self.config = config
        print(f"initialized service for {self.image}:{self.version}")
        self.check_for_running_containers()

    def check_for_running_containers(self) -> None:
        """Checks for a running container for this service and uses it instead
        of launching a new one
        """
        containers = self.client.containers.list(all=True)
        container_name = f"companion_{self.image}".replace("/", "")
        for container in containers:
            if self.image in str(container.image) or container.name == container_name:
                self.container = container
                self.statusfetcher = StatusFetcher(container)

    def get_local_tags(self) -> List[str]:
        """Finds all tags available locally for this service's image

        Returns:
            list: list of tags
        """
        tags = []
        for image in self.client.images.list(self.image):
            tags.extend(image.tags)
        try:
            formatted_tags = [name.split(":")[-1] for name in tags if self.image in name]
            return formatted_tags
        except Exception as error:
            print(f"unable to format tags! {error}")
            return []

    def update(self) -> None:
        # poll once every 10 s
        if time.time() - self.last_tag_update > 10:
            self.last_tag_update = time.time()
            self.available_tags = self.get_local_tags()
        if self.enabled:
            # should be running but isn't
            if not self.is_running():
                self.start()
            # is running but the wrong version

            # This could be an elif if not for the assert...
            else:
                assert self.container is not None, "container is running AND None!"
                if self.version not in [tag.split(":")[-1] for tag in self.container.image.tags]:
                    self.restart()
        else:
            # is running but shouldn't
            if self.is_running():
                self.stop()

    def stop(self) -> None:
        """Stops service"""
        print("trying to stop ...")
        if self.container and self.is_running():
            self.stored_logs = self.container.logs()
            self.container.stop(timeout=2)
            self.container.remove()
            self.container = None
        else:
            print("skipped")

    def start(self) -> None:
        """Starts service"""
        self.launch()

    def restart(self) -> None:
        """restarts service"""
        self.stop()
        self.start()

    def is_running(self) -> bool:
        """Checks if the service is running properly

        Returns:
            bool: Service is running
        """
        if self.container is None:
            return False
        self.container.reload()

        return bool(self.container.status == "running")

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Gets the status for the running container

        Returns:
            Optional[dict]: TODO: fill this.
        """
        if self.statusfetcher:
            image = None
            if self.container:
                image = self.container.image.history()[0]
                image["age"] = time.time() - image["Created"]
            return {
                "stats": self.statusfetcher.status,
                "version": self.version,
                "available_tags": self.available_tags,
                "config": self.config,
                "id": self.container.id if self.container is not None else None,
                "image": image,
                "running": self.container.status == "running" if self.container is not None else False,
                "tag": self.version,
            }
        return None

    def get_logs(self) -> Optional[str]:
        """Fetchs logs from the contaienr

        Returns:
            str: log of the current container if running, logs of last instances if not.
        """
        if self.container is not None:
            return str(self.container.logs())
        else:
            return self.stored_logs

    def get_top(self) -> Dict[Any, Any]:
        """Reads the running processes in this docker

        Returns:
            Dict: all running processes as a json-formatted output of 'ps', None if not available
        """
        if self.container is None:
            return {}
        return dict(self.container.top())

    def disable(self) -> None:
        """Disables the service"""
        self.enabled = False
        self.config["enabled"] = False

    def enable(self) -> None:
        """Enables the service"""
        self.starts = 0
        self.enabled = True
        self.config["enabled"] = True

    def set_version(self, version: str) -> bool:
        """Change running version of the service

        Args:
            version: the new version(tag) to use

        Returns:
            bool: If version was changed sucessfully
        """
        if version not in self.available_tags:
            print("version not available locally!")
            print(self.available_tags)
            return False
        else:
            self.version = version
            print(f"setting version to {version}")
            self.restart()
            return True

    def launch(self) -> None:
        """Launches a container for the service"""
        print("launching", self.image)
        self.starts += 1
        # Re-launch existing container
        if self.container:
            if self.version in [tag.split(":")[-1] for tag in self.container.image.tags]:
                self.container.start()
                return
            else:
                self.container.remove()

        # Launch new container
        try:
            image_name = f"{self.config['image']}:{self.version}"
            print(f"trying to start {image_name}")
            container_name = f"companion_{self.image}".replace("/", "")
            # Otherwise, start a new one
            self.container = self.client.containers.run(
                image_name,
                name=container_name,
                auto_remove=False,
                volumes=self.config["binds"],
                ports=self.config["ports"],
                network=self.config["network"],
                tty=False,
                detach=True,
            )
            print("done")
        except Exception as error:
            print("failed to launch ", self.image, error)
        if self.container:
            self.statusfetcher = StatusFetcher(self.container)
