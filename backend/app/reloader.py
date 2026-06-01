from typing import Protocol


class Reloader(Protocol):
    def restart(self, container: str) -> None: ...


class DockerReloader:
    def __init__(self, client=None):
        if client is None:
            import docker

            client = docker.from_env()
        self._client = client

    def restart(self, container: str) -> None:
        self._client.containers.get(container).restart()
