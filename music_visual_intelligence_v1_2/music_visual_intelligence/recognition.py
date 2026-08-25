from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from zipfile import ZipFile

ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
FPCALC_RELEASE_URL = (
    "https://github.com/acoustid/chromaprint/releases/download/"
    "v1.6.1/chromaprint-fpcalc-1.6.1-windows-x86_64.zip"
)
MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"
COVER_ART_BASE = "https://coverartarchive.org"


class RecognitionError(RuntimeError):
    pass


@dataclass
class SongIdentity:
    matched: bool
    confidence: float
    acoustid: str | None = None
    musicbrainz_recording_id: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    release_id: str | None = None
    release_group_id: str | None = None
    release_date: str | None = None
    cover_url: str | None = None
    cover_local_path: str | None = None
    source: str = "acoustid+musicbrainz"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_fpcalc_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "fpcalc" / "fpcalc.exe"


def find_fpcalc(explicit: str | Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.getenv("MVI_FPCALC")
    if env:
        candidates.append(Path(env))
    candidates.append(_default_fpcalc_path())
    system_path = shutil.which("fpcalc")
    if system_path:
        candidates.append(Path(system_path))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def download_fpcalc(destination: str | Path | None = None) -> Path:
    if platform.system() != "Windows":
        raise RecognitionError(
            "Automatic fpcalc bootstrap currently targets Windows x86_64."
        )

    destination = Path(destination) if destination else _default_fpcalc_path()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "fpcalc.zip"
        request = Request(
            FPCALC_RELEASE_URL,
            headers={"User-Agent": "MusicVisualIntelligence/0.1.2"},
        )
        try:
            with urlopen(request, timeout=60) as response, archive.open("wb") as out:
                shutil.copyfileobj(response, out)
        except (HTTPError, URLError) as exc:
            raise RecognitionError(f"Could not download fpcalc: {exc}") from exc

        with ZipFile(archive) as zf:
            members = [
                name for name in zf.namelist()
                if Path(name).name.lower() == "fpcalc.exe"
            ]
            if not members:
                raise RecognitionError(
                    "Downloaded Chromaprint archive does not contain fpcalc.exe."
                )

            with zf.open(members[0]) as source, destination.open("wb") as out:
                shutil.copyfileobj(source, out)

    return destination


def run_fpcalc(
    audio_path: str | Path,
    fpcalc_path: str | Path | None = None,
) -> tuple[float, str]:
    executable = find_fpcalc(fpcalc_path)
    if executable is None:
        raise RecognitionError(
            "fpcalc was not found. Run `mvi setup-fpcalc` or set MVI_FPCALC."
        )

    command = [str(executable), "-json", "-length", "120", str(Path(audio_path))]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise RecognitionError("fpcalc executable could not be launched.") from exc
    except subprocess.CalledProcessError as exc:
        raise RecognitionError(
            f"fpcalc failed with exit code {exc.returncode}: {exc.stderr.strip()}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RecognitionError(
            "fpcalc timed out while generating the fingerprint."
        ) from exc

    try:
        payload = json.loads(result.stdout)
        duration = float(payload["duration"])
        fingerprint = str(payload["fingerprint"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise RecognitionError("fpcalc returned invalid fingerprint JSON.") from exc

    return duration, fingerprint


def acoustid_lookup(
    fingerprint: str,
    duration: float,
    client_key: str,
    *,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = {
        "client": client_key,
        "duration": str(round(duration)),
        "fingerprint": fingerprint,
        "meta": "recordings+releasegroups+releases",
        "format": "json",
    }

    request = Request(
        ACOUSTID_URL + "?" + urlencode(params),
        headers={"User-Agent": "MusicVisualIntelligence/0.1.2"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RecognitionError(f"AcoustID request failed: {exc}") from exc

    if payload.get("status") != "ok":
        raise RecognitionError(
            f"AcoustID returned status: {payload.get('status')}"
        )

    return payload.get("results", [])


class MusicBrainzClient:
    def __init__(
        self,
        app_name: str = "MusicVisualIntelligence",
        version: str = "0.1.2",
        contact: str = "local-project",
        min_interval: float = 1.1,
    ) -> None:
        self.user_agent = f"{app_name}/{version} ({contact})"
        self.min_interval = min_interval
        self._last_request = 0.0

    def _get(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_request)
        if wait > 0:
            time.sleep(wait)

        url = f"{MUSICBRAINZ_BASE}/{path}"
        query = urlencode(params or {})
        if query:
            url += "?" + query

        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise RecognitionError(
                f"MusicBrainz request failed: {exc}"
            ) from exc
        finally:
            self._last_request = time.monotonic()

        return payload

    def recording(self, recording_id: str) -> dict[str, Any]:
        return self._get(
            f"recording/{recording_id}",
            {"inc": "artist-credits+releases+release-groups+isrcs"},
        )


def choose_best_acoustid(
    results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not results:
        return None
    return max(results, key=lambda item: float(item.get("score", 0.0)))


def identify_file(
    audio_path: str | Path,
    *,
    client_key: str | None = None,
    fpcalc_path: str | Path | None = None,
    musicbrainz_client: MusicBrainzClient | None = None,
) -> SongIdentity:
    client_key = client_key or os.getenv("MVI_ACOUSTID_CLIENT")
    if not client_key:
        raise RecognitionError(
            "AcoustID client key is missing. Set MVI_ACOUSTID_CLIENT."
        )

    duration, fingerprint = run_fpcalc(audio_path, fpcalc_path)
    results = acoustid_lookup(fingerprint, duration, client_key)
    best = choose_best_acoustid(results)

    if best is None:
        return SongIdentity(
            matched=False,
            confidence=0.0,
        )

    score = float(best.get("score", 0.0))
    recordings = best.get("recordings") or []
    recording_id = recordings[0].get("id") if recordings else None

    if not recording_id:
        return SongIdentity(
            matched=True,
            confidence=score,
            acoustid=best.get("id"),
            source="acoustid",
        )

    client = musicbrainz_client or MusicBrainzClient()
    mb = client.recording(recording_id)

    artist_parts = []
    for item in mb.get("artist-credit") or []:
        artist = (item.get("artist") or {}).get("name")
        if artist:
            artist_parts.append(artist)
        artist_parts.append(item.get("joinphrase", ""))

    releases = mb.get("releases") or []
    release = releases[0] if releases else {}
    release_group = release.get("release-group") or {}

    return SongIdentity(
        matched=True,
        confidence=score,
        acoustid=best.get("id"),
        musicbrainz_recording_id=recording_id,
        title=mb.get("title"),
        artist="".join(artist_parts).strip() or None,
        album=release.get("title"),
        release_id=release.get("id"),
        release_group_id=release_group.get("id"),
        release_date=release.get("date"),
    )


def cover_url_for_release(release_id: str, size: int = 500) -> str:
    size = size if size in {250, 500, 1200} else 500
    return f"{COVER_ART_BASE}/release/{release_id}/front-{size}"
