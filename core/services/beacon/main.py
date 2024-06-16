#!/usr/bin/env python3
import argparse
import asyncio
import datetime
import itertools
import logging
import os
import pathlib
import shlex
import shutil
import signal
import socket
import subprocess
from typing import Any, Dict, List, Optional

import psutil
from commonwealth.settings.manager import Manager
from commonwealth.utils.apis import PrettyJSONResponse
from commonwealth.utils.logs import init_logger
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version
from loguru import logger
from uvicorn import Config, Server
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

from settings import ServiceTypes, SettingsV5
from typedefs import InterfaceType, IpInfo, MdnsEntry

SERVICE_NAME = "beacon"

TLS_CERT_PATH = "/etc/blueos/nginx/blueos.crt"
TLS_KEY_PATH = "/etc/blueos/nginx/blueos.key"


class AsyncRunner:
    def __init__(self, ip_version: IPVersion, interface: str, interface_name: str) -> None:
        self.ip_version = ip_version
        self.aiozc: Optional[AsyncZeroconf] = None
        self.interface: str = interface
        self.services: List[AsyncServiceInfo] = []
        self.interface_name = interface_name

    def add_services(self, service: AsyncServiceInfo) -> None:
        self.services.append(service)

    def get_services(self) -> List[MdnsEntry]:
        return [
            MdnsEntry(
                ip=self.interface,
                fullname=service.name,
                hostname=service.name.split(".")[0],
                service_type=service.name.split(".")[1],
                interface=self.interface_name,
                interface_type=InterfaceType.guess_from_name(self.interface_name),
            )
            for service in self.services
        ]

    async def register_services(self) -> None:
        self.aiozc = AsyncZeroconf(ip_version=self.ip_version, interfaces=[self.interface])  # type: ignore
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
        return {str(service) for service in self.services} == {
            str(service) for service in other.services
        } and self.interface == other.interface

    def __repr__(self) -> str:
        return f"Runner on {self.interface}, serving {[service.name for service in self.services]}."


class Beacon:
    DEFAULT_HOSTNAME = "blueos"

    def __init__(self) -> None:
        self.runners: Dict[str, AsyncRunner] = {}
        try:
            self.manager = Manager(SERVICE_NAME, SettingsV5)
        except Exception as e:
            logger.warning(f"failed to load configuration file ({e}), loading defaults")
            self.load_default_settings()

        # manager still returns "valid" settings even if file is absent, so we check for the "default" field
        # TODO: fix after https://github.com/bluerobotics/BlueOS-docker/issues/880 is solved
        if self.manager.settings.default is None:
            logger.warning("No configuration found, loading defaults...")
            self.load_default_settings()
        self.settings = self.manager.settings
        self.service_types = self.load_service_types()

    def load_default_settings(self) -> None:
        current_folder = pathlib.Path(__file__).parent.resolve()
        default_settings_file = current_folder / "default-settings.json"
        logger.debug("loading settings from ", default_settings_file)
        self.manager = Manager(SERVICE_NAME, SettingsV5, load=False)
        self.manager.settings = self.manager.load_from_file(SettingsV5, default_settings_file)
        self.manager.save()

    def load_service_types(self) -> Dict[str, ServiceTypes]:
        """
        load services from settings as a dictionary
        """
        services = {}
        for service in self.settings.advertisement_types:
            services[service.name] = service
        return services

    def set_hostname(self, hostname: str) -> None:
        self.manager.settings.default.domain_names = [hostname]
        for interface in self.manager.settings.interfaces:
            match InterfaceType.guess_from_name(interface.name):
                case InterfaceType.WIRED | InterfaceType.USB:
                    interface.domain_names = [hostname, self.DEFAULT_HOSTNAME]  # let's keep our default just in case
                case InterfaceType.WIFI:
                    interface.domain_names = [f"{hostname}-wifi"]
                case InterfaceType.HOTSPOT:
                    interface.domain_names = [f"{hostname}-hotspot"]
        self.manager.save()

    def get_hostname(self) -> str:
        try:
            return self.manager.settings.default.domain_names[0] or self.DEFAULT_HOSTNAME
        except Exception:
            return self.DEFAULT_HOSTNAME

    def set_vehicle_name(self, name: str) -> None:
        self.manager.settings.vehicle_name = name
        self.manager.save()

    def get_vehicle_name(self) -> str:
        return self.manager.settings.vehicle_name or "BlueROV2"

    def get_enable_tls(self) -> bool:
        # TODO: return what's in settings or assume no...this may change in the future
        return self.manager.settings.use_tls or False

    def set_enable_tls(self, enable_tls: bool) -> None:
        # handle enabling/disabling tls
        if not enable_tls and self.get_enable_tls():
            # tls is currently enabled and we need to disable
            # change nginx config
            self.generate_new_nginx_config(use_tls=False)
            # validate config
            if not self.nginx_config_is_valid():
                raise SystemError("Unable to validate staged Nginx config")
            # bounce nginx
            self.nginx_promote_config(keep_backup=True)
            # remove old cert
            os.unlink(TLS_CERT_PATH)
            os.unlink(TLS_KEY_PATH)
        elif enable_tls and not self.get_enable_tls():
            # tls is currently disabled and we need to enable
            # generate cert
            self.generate_cert()
            # change nginx config
            self.generate_new_nginx_config(use_tls=True)
            # validate config
            if not self.nginx_config_is_valid():
                raise SystemError("Unable to validate staged Nginx config")
            # bounce nginx
            self.nginx_promote_config(keep_backup=True)
        self.manager.settings.use_tls = enable_tls
        self.manager.save()

    def generate_cert(self) -> None:
        """
        Generates the TLS certificate for the current vehicle hostname and stores in persistent storage
        """
        # get the hostname
        current_hostname = self.get_hostname()
        alt_names = []
        alt_names.append(f"DNS:{current_hostname}")
        alt_names.append(f"DNS:{current_hostname}-wifi")
        alt_names.append(f"DNS:{current_hostname}-hotspot")
        alt_names.append("IP:192.168.2.2")

        # shell out to openssl to get the cert
        try:
            subprocess.check_call(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:4096",
                    "-sha256",
                    "-days",
                    "1825",
                    "-nodes",
                    "-keyout",
                    TLS_KEY_PATH,
                    "-out",
                    TLS_CERT_PATH,
                    "-subj",
                    shlex.quote(f"/CN={self.DEFAULT_HOSTNAME}"),
                    "-addext",
                    shlex.quote(f"subjectAltName={','.join(alt_names)}"),
                ],
                shell=False,
            )
        except subprocess.CalledProcessError as ex:
            raise SystemError("Unable to generate certificates") from ex

    def generate_new_nginx_config(
        self, config_path: str = "/etc/blueos/nginx/nginx.conf.ondeck", use_tls: bool = False
    ) -> None:
        """
        Generates a new nginx config file at the path specified
        """
        # use the templates for simplicity now
        # also, the templates are in core's tools directory but the live config lives in /etc/blueos/nginx
        # TODO: the user may have changed the config, so we should parse and update as needed
        if use_tls:
            shutil.copy("/home/pi/tools/nginx/nginx_tls.conf.template", config_path, follow_symlinks=False)
        else:
            shutil.copy("/home/pi/tools/nginx/nginx.conf.template", config_path, follow_symlinks=False)

    def nginx_config_is_valid(self, config_path: str = "/etc/blueos/nginx/nginx.conf.ondeck") -> bool:
        """
        Returns true if the nginx config file is valid
        """
        try:
            subprocess.check_call(["nginx", "-t", "-c", config_path], shell=False)
            return True
        except subprocess.CalledProcessError:
            # got a non-zero return code indicating the config was not valid
            return False

    def nginx_promote_config(
        self,
        config_path: str = "/etc/blueos/nginx/nginx.conf",
        new_config_path: str = "/etc/blueos/nginx/nginx.conf.ondeck",
        keep_backup: bool = False,
    ) -> None:
        """
        Moves the file at new_config_path to config_path and bounces nginx, optionally keeping a backup of config_path
        """
        # do both files exist
        if not os.path.exists(config_path):
            raise FileNotFoundError("Old config not found")
        if not os.path.isfile(new_config_path):
            raise FileNotFoundError("New config not found")

        if keep_backup:
            shutil.copyfile(
                config_path,
                f"{config_path}_backup_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                follow_symlinks=False,
            )

        # move it
        os.unlink(config_path)
        os.rename(new_config_path, config_path)

        # reload nginx config by getting the PID of the master process and sending a SIGHUP
        if not os.path.exists("/run/nginx.pid"):
            raise SystemError("No nginx master PID found")
        with open("/run/nginx.pid", "r", encoding="utf-8") as pidf:
            nginx_pid = int(pidf.read())
            os.kill(nginx_pid, signal.SIGHUP)

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
            if any(interface.startswith(filter_) for filter_ in self.settings.blacklist):
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
                        runner = AsyncRunner(IPVersion.V4Only, interface=ip, interface_name=interface_name)
                        logger.info(f"Created runner {runner_name} for {ip}")
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
                        runner = AsyncRunner(IPVersion.V4Only, interface=ip, interface_name=interface_name)
                        logger.info(f"Created runner for interface {interface.name}, broadcasting {domain} on {ip}")
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
            self.settings = self.manager.settings
            self.service_types = self.load_service_types()

            default_runners = self.create_default_runners()
            user_runners = self.create_user_runners()

            all_runners = {**default_runners, **user_runners}
            for runner in all_runners.values():
                logger.info(runner)

            for runner_name, runner in all_runners.items():
                if runner_name not in self.runners:
                    try:
                        await runner.register_services()
                        self.runners[runner_name] = runner
                    except Exception as e:
                        logger.warning(e)
                elif self.runners[runner_name] != runner:
                    # unregister old one and register new one
                    logger.info(f"runner {runner_name} has changed, updating runner...")
                    await self.runners[runner_name].unregister_services()
                    self.runners[runner_name] = runner
                    await runner.register_services()

            await asyncio.sleep(10)

    async def stop(self) -> None:
        await asyncio.gather(*[runner.unregister_services() for runner in self.runners.values()])


logging.basicConfig(level=logging.DEBUG)
init_logger(SERVICE_NAME)

app = FastAPI(
    title="Beacon API",
    description="Beacon is responsible for publishing mDNS domains.",
    default_response_class=PrettyJSONResponse,
    debug=True,
)

beacon = Beacon()


@app.get("/services", response_model=List[MdnsEntry], summary="Current domains broadcasted.")
@version(1, 0)
def get_services() -> Any:
    return list(itertools.chain.from_iterable([runner.get_services() for runner in beacon.runners.values()]))


@app.post("/hostname", summary="Set the hostname for mDNS.")
@version(1, 0)
def set_hostname(hostname: str) -> Any:
    return beacon.set_hostname(hostname)


@app.get("/hostname", summary="Get hostname for mDNS.")
@version(1, 0)
def get_hostname() -> Any:
    return beacon.get_hostname()


@app.post("/vehicle_name", summary="Set the vehicle name")
@version(1, 0)
def set_vehicle_name(name: str) -> Any:
    return beacon.set_vehicle_name(name)


@app.get("/vehicle_name", response_model=str, summary="Get the vehicle name")
@version(1, 0)
def get_vehicle_name() -> Any:
    return beacon.get_vehicle_name()


@app.get("/ip", response_model=IpInfo, summary="Ip Information")
@version(1, 0)
def get_ip(request: Request) -> Any:
    """Returns the IP address of the client and of the network interface serving the client"""
    try:
        return IpInfo(client_ip=request.headers["x-real-ip"], interface_ip=request.headers["x-interface-ip"])
    except KeyError:
        # We're not going through Nginx for some reason
        return IpInfo(client_ip=request.scope["client"][0], interface_ip=request.scope["server"][0])


@app.get("/use_tls", summary="Get whether TLS should be enabled")
@version(1, 0)
def get_enable_tls() -> bool:
    return beacon.get_enable_tls()


@app.post("/use_tls", summary="Set whether TLS should be enbabled")
@version(1, 0)
def set_enable_tls(enable_tls: bool) -> Any:
    return beacon.set_enable_tls(enable_tls)


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


@app.get("/")
async def root() -> Any:
    html_content = """
    <html>
        <head>
            <title>Beacon Service</title>
        </head>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger("zeroconf").setLevel(logging.DEBUG)

    logger.info("Starting Beacon Service.")

    loop = asyncio.new_event_loop()

    config = Config(app=app, loop=loop, host="0.0.0.0", port=9111, log_config=None)
    server = Server(config)

    loop.create_task(beacon.run())
    loop.run_until_complete(server.serve())
    loop.run_until_complete(beacon.stop())
