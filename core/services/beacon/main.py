#!/usr/bin/env python3
import argparse
import asyncio
import logging
import pathlib
import socket
from typing import Any, Dict, List, Optional

import psutil
from commonwealth.settings.manager import Manager
from commonwealth.utils.logs import get_new_log_path
from loguru import logger
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from settings import ServiceTypes, SettingsV2

SERVICE_NAME = "beacon"


class AsyncRunner:
    def __init__(self, ip_version: IPVersion, interfaces: List[str]) -> None:
        self.ip_version = ip_version
        self.aiozc: Optional[AsyncZeroconf] = None
        self.interfaces: List[str] = interfaces
        self.services: List[AsyncServiceInfo] = []

    def add_services(self, service: AsyncServiceInfo) -> None:
        logger.info("Adding services:")
        logger.info(service)
        self.services.append(service)

    async def register_services(self) -> None:
        self.aiozc = AsyncZeroconf(ip_version=self.ip_version, interfaces=[self.interfaces])  # type: ignore
        tasks = [self.aiozc.async_register_service(info, cooperating_responders=True, ttl=25) for info in self.services]
        background_tasks = await asyncio.gather(*tasks)
        await asyncio.gather(*background_tasks)
        logger.info("Finished registration, press Ctrl-C to exit...")

    async def unregister_services(self) -> None:
        assert self.aiozc is not None
        tasks = [self.aiozc.async_unregister_service(info) for info in self.services]
        background_tasks = await asyncio.gather(*tasks)
        await asyncio.gather(*background_tasks)
        await self.aiozc.async_close()

    def __eq__(self, other: Any) -> bool:
        return {str(service) for service in self.services} == {str(service) for service in other.services} and set(
            self.interfaces
        ) == set(other.interfaces)

    def __repr__(self) -> str:
        return f"Runner on {self.interfaces}, serving {[service.name for service in self.services]}."


class Beacon:
    def __init__(self) -> None:
        self.runners: Dict[str, AsyncRunner] = {}
        self.manager = Manager(SERVICE_NAME, SettingsV2)
        # manager still returns "valid" settings even if file is absent, so we check for the "default" field
        # TODO: fix after https://github.com/bluerobotics/BlueOS-docker/issues/880 is solved
        if self.manager.settings.default is None:
            logger.warning("No configuration found, loading defaults...")
            current_folder = pathlib.Path(__file__).parent.resolve()
            default_settings_file = current_folder / "default-settings.json"
            logger.debug("loading settings from ", default_settings_file)
            self.manager.settings = self.manager.load_from_file(SettingsV2, default_settings_file)
            self.manager.save()
        self.settings = self.manager.settings
        self.service_types = self.load_service_types()

    def load_service_types(self) -> Dict[str, ServiceTypes]:
        """
        load services from settings as a dictionary
        """
        services = {}
        for service in self.settings.advertisement_types:
            services[service.name] = service
        return services

    def create_async_service_infos(
        self, interface: str, service_name: str, domain_name: str, ip: str
    ) -> AsyncServiceInfo:
        """
        Create A list of AsyncServiceInfo() for the given interface and service
        Each domain results in a new service
        """
        service = self.service_types[service_name]
        try:
            return AsyncServiceInfo(
                f"{service.name}.{service.protocol}.local.",
                f"{domain_name}.{service.name}.{service.protocol}.local.",
                addresses=[socket.inet_aton(ip)],
                port=service.port,
                properties=service.get_properties(),
                server=f"{domain_name}.local.",
            )
        except Exception as e:
            logger.warning(f"Error creating AsyncServiceInfo {service.name} at {interface}: {e}")
            raise e

    def get_filtered_interfaces(self) -> List[psutil._common.snicaddr]:
        """
        Returns interfaces found that are up and filters them using the blacklist in settings
        """
        stats = psutil.net_if_stats()

        available_networks = []
        for interface in stats.keys():
            if any(interface.startswith(filter) for filter in self.settings.blacklist):
                continue
            if interface in stats and getattr(stats[interface], "isup"):
                available_networks.append(interface)

        return available_networks

    def create_default_runners(self) -> Dict[str, AsyncRunner]:
        """
        This creates default runners with the name blueos-{interface}-{count}
        used for emergencies.
        """

        default_runners = {}
        for interface_name in self.get_filtered_interfaces():
            count = 1
            interface = self.settings.get_interface_or_create_default(interface_name)
            for ip in interface.get_ip_strs():
                for domain in self.settings.default.domain_names:
                    runner_name = f"{domain}-{interface_name}-{count}"
                    try:
                        runner = AsyncRunner(IPVersion.V4Only, interfaces=ip)
                        logger.info(f"Created runner {runner_name}")
                    except Exception as e:
                        logger.warning(f"Error creating {runner_name}: {e}, skipping this interface")
                        continue
                    for service in self.settings.default.advertise:
                        try:
                            runner.add_services(self.create_async_service_infos(interface, service, runner_name, ip))
                        except ValueError as e:
                            logger.warning(f"Error adding service for {interface.name}-{service}: {e}, skipping.")
                    default_runners[runner_name] = runner
                    count += 1
        return default_runners

    def create_user_runners(self) -> Dict[str, AsyncRunner]:
        """
        Creates runners specified in the "interfaces" sections of settings.json
        """
        runners = {}
        for interface_name in self.get_filtered_interfaces():
            interface = self.settings.get_interface_or_create_default(interface_name)
            for ip in interface.get_ip_strs():
                for domain in interface.domain_names:
                    runner = None
                    try:
                        runner = AsyncRunner(IPVersion.V4Only, interfaces=ip)
                        logger.info(f"Created runner for interface {interface.name}, broadcasting on {ip}")
                    except Exception as e:
                        logger.warning(f"Error creating runner for {interface.name}: {e}, skipping this interface")
                        continue

                    for service in interface.advertise:
                        try:
                            runner.add_services(self.create_async_service_infos(interface, service, domain, ip))
                        except ValueError as e:
                            logger.warning(f"Error adding service for {interface.name}-{service}: {e}, skipping.")
                    runners[f"{interface_name}-{domain}"] = runner
        return runners

    async def run(self) -> None:
        """
        This is the "main loop" from Beacon.
        """
        while True:
            # re-load settings in case something changed
            self.manager.load()
            self.service_types = self.load_service_types()

            default_runners = self.create_default_runners()
            user_runners = self.create_user_runners()

            all_runners = {**default_runners, **user_runners}
            for runner in all_runners.values():
                logger.info(runner)

            for runner_name, runner in all_runners.items():
                if runner_name not in self.runners:
                    self.runners[runner_name] = runner
                    await runner.register_services()
                elif self.runners[runner_name] != runner:
                    # unregister old one and register new one
                    logger.info(f"runner {runner_name} has changed, updating runner...")
                    await self.runners[runner_name].unregister_services()
                    self.runners[runner_name] = runner
                    await runner.register_services()

            self.manager.save()
            await asyncio.sleep(10)

    async def stop(self) -> None:
        await asyncio.gather(*[runner.unregister_services() for runner in self.runners.values()])


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.add(get_new_log_path(SERVICE_NAME))

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger("zeroconf").setLevel(logging.DEBUG)

    beacon = Beacon()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(beacon.run())
    except KeyboardInterrupt:
        loop.run_until_complete(beacon.stop())
