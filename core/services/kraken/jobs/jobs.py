import asyncio
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp
from jobs.exceptions import JobIsRunning, JobNotFound
from jobs.models import Job, JobStatus
from jobs.stream import JobStream
from loguru import logger


class JobsManager:
    _jobs: List[Job] = []
    _executing_job: Optional[Job] = None
    _streams: Dict[str, JobStream] = {}

    def __init__(self) -> None:
        self.is_running = True
        self.base_host = ""

    async def execute_job(self, job: Job) -> None:
        job_name = f"{job.method.value} - {job.route}"
        logger.info(f"Executing job {job_name}")
        stream = self._streams[job.id]
        async with aiohttp.ClientSession() as session:
            for i in range(job.retries):
                try:
                    async with session.request(
                        method=job.method, url=f"{self.base_host}/{job.route}", json=job.body
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.content.iter_any():
                            stream.publish(chunk)
                        job.status = JobStatus.SUCCESS
                        return
                except Exception:
                    logger.warning(f"Failed job {job_name} attempt {i + 1}/{job.retries}")
                    stream.reset()
                    await asyncio.sleep(5)
            job.status = JobStatus.ERROR
            logger.error(f"Job {job_name} failed to be executed")

    async def start(self) -> None:
        while self.is_running:
            await asyncio.sleep(1)
            if JobsManager._jobs:
                JobsManager._executing_job = JobsManager._jobs.pop(0)
                JobsManager._executing_job.status = JobStatus.RUNNING
                stream = JobsManager._streams[JobsManager._executing_job.id]
                try:
                    await self.execute_job(JobsManager._executing_job)
                finally:
                    stream.close()
                    JobsManager._streams.pop(JobsManager._executing_job.id, None)
                    JobsManager._executing_job = None

    async def stop(self) -> None:
        self.is_running = False

    def set_base_host(self, host: str) -> None:
        self.base_host = host

    @classmethod
    def add(cls, job: Job) -> None:
        cls._streams[job.id] = JobStream()
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
    def stream(cls, identifier: str) -> AsyncGenerator[bytes, None]:
        cls.get_by_identifier(identifier)
        return cls._streams[identifier].subscribe()

    @classmethod
    def delete(cls, identifier: str) -> None:
        cls.get_by_identifier(identifier)
        job = next((job for job in cls._jobs if job.id == identifier), None)
        if job:
            cls._jobs.remove(job)
            stream = cls._streams.pop(identifier, None)
            if stream:
                stream.close()
        elif cls._executing_job and cls._executing_job.id == identifier:
            raise JobIsRunning(f"Cannot delete job {identifier} while it is running")
