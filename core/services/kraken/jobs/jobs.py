import asyncio
from typing import List, Optional

import aiohttp
from loguru import logger

from jobs.exceptions import JobNotFound
from jobs.models import Job


class JobsManager:
    _jobs: List[Job] = []
    _executing_job: Optional[Job] = None

    def __init__(self) -> None:
        self.is_running = True
        self.base_host = ""

    async def execute_job(self, job: Job) -> None:
        job_name = f"{job.method.value} - {job.route}"
        logger.info(f"Executing job {job_name}")
        async with aiohttp.ClientSession() as session:
            for i in range(job.retries):
                try:
                    async with session.request(
                        method=job.method, url=f"{self.base_host}/{job.route}", json=job.body
                    ) as response:
                        response.raise_for_status()
                        await response.read()
                        return
                except Exception:
                    logger.warning(f"Failed job {job_name} attempt {i + 1}/{job.retries}")
                    await asyncio.sleep(5)
            logger.error(f"Job {job_name} failed to be executed")

    async def start(self) -> None:
        while self.is_running:
            await asyncio.sleep(1)
            if self._jobs:
                self._executing_job = self._jobs.pop(0)
                await self.execute_job(self._executing_job)
                self._executing_job = None

    async def stop(self) -> None:
        self.is_running = False

    def set_base_host(self, host: str) -> None:
        self.base_host = host

    @classmethod
    def add(cls, job: Job) -> None:
        cls._jobs.append(job)

    @classmethod
    def get(cls) -> List[Job]:
        return ([cls._executing_job] if cls._executing_job else []) + cls._jobs

    @classmethod
    def get_by_identifier(cls, identifier: str) -> Job:
        job = next((job for job in cls.get() if job.id == identifier), None)
        if job is None:
            raise JobNotFound(f"Job with id {identifier} not found")
        return job

    @classmethod
    def delete(cls, identifier: str) -> None:
        job = cls.get_by_identifier(identifier)
        cls._jobs.remove(job)
