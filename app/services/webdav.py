from pathlib import Path
from webdav4.client import Client
from app.config import get_settings


def get_client() -> Client:
    settings = get_settings()
    return Client(
        base_url=settings.webdav_url,
        auth=(settings.webdav_user, settings.webdav_password),
    )


def list_files(client: Client) -> set[str]:
    """Gibt die Menge aller Dateinamen im WebDAV-Ordner zurück."""
    items = client.ls("", detail=False)
    return {Path(p).name for p in items if not p.endswith("/")}


def upload_file(client: Client, local_path: Path, remote_name: str) -> None:
    """Lädt eine lokale Datei in den WebDAV-Ordner hoch."""
    with open(local_path, "rb") as f:
        client.upload_fileobj(f, remote_name)


def delete_file(client: Client, remote_name: str) -> None:
    """Löscht eine Datei aus dem WebDAV-Ordner."""
    client.remove(remote_name)
