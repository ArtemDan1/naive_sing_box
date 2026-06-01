from unittest.mock import MagicMock

from app.reloader import DockerReloader


def test_restart_calls_docker_container_restart():
    fake_client = MagicMock()
    r = DockerReloader(client=fake_client)
    r.restart("singbox")
    fake_client.containers.get.assert_called_once_with("singbox")
    fake_client.containers.get.return_value.restart.assert_called_once()
