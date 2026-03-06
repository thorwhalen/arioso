"""Google Lyria 2 adapter.

Uses the ``google-cloud-aiplatform`` SDK when available, falling back to
raw REST calls against the Vertex AI prediction endpoint.
"""

import base64
import os

from arioso.base import AudioResult, Song
from arioso.platforms._base_adapter import BaseRestAdapter

_FIXED_DURATION = 30.0
_SAMPLE_RATE = 48000
_DEFAULT_LOCATION = "us-central1"
_DEFAULT_MODEL = "lyria-002"


def _get_endpoint_url(*, project: str, location: str, model: str) -> str:
    """Build the Vertex AI prediction endpoint URL."""
    return (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/"
        f"publishers/google/models/{model}:predict"
    )


def _build_request_body(
    prompt: str,
    *,
    negative_prompt: str = "",
    seed: int = None,
    batch_size: int = 1,
) -> dict:
    """Construct the JSON body for the Vertex AI predict call."""
    instance = {"prompt": prompt}
    if negative_prompt:
        instance["negative_prompt"] = negative_prompt

    parameters = {"sampleCount": batch_size}
    if seed is not None:
        parameters["seed"] = seed

    return {"instances": [instance], "parameters": parameters}


class Adapter(BaseRestAdapter):
    """Google Lyria 2 adapter with SDK-first, REST-fallback strategy."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._use_sdk = None  # tri-state: None=unknown, True/False

    def _try_sdk_generate(self, body: dict, *, project: str, location: str, model: str):
        """Attempt generation via the google-cloud-aiplatform SDK.

        Returns raw predictions list on success, or raises ImportError /
        Exception to signal fallback.
        """
        from google.cloud import aiplatform

        aiplatform.init(project=project, location=location)

        endpoint_name = (
            f"projects/{project}/locations/{location}/"
            f"publishers/google/models/{model}"
        )
        endpoint = aiplatform.Endpoint(endpoint_name)
        response = endpoint.predict(
            instances=body["instances"],
            parameters=body["parameters"],
        )
        return response.predictions

    def _rest_generate(self, body: dict, *, project: str, location: str, model: str):
        """Generate via raw REST POST to Vertex AI."""
        url = _get_endpoint_url(project=project, location=location, model=model)

        # Prefer google-auth for automatic credential refresh
        headers = {}
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
            headers["Authorization"] = f"Bearer {credentials.token}"
        except (ImportError, Exception):
            # Fall back to bearer token from env
            token = os.environ.get(self.config["auth"]["env_var"], "")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        response = self.session.post(url, json=body, headers=headers)
        response.raise_for_status()
        return response.json().get("predictions", [])

    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        seed: int = None,
        model: str = _DEFAULT_MODEL,
        batch_size: int = 1,
        **kwargs,
    ) -> Song:
        """Generate music using Google Lyria 2.

        Args:
            prompt: Text description of desired music.
            negative_prompt: Elements to avoid in the generation.
            seed: Random seed for reproducibility.
            model: Model version identifier.
            batch_size: Number of samples to generate.

        Returns:
            A Song with WAV audio bytes (fixed 30 s duration at 48 kHz).
        """
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)

        body = _build_request_body(
            prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            batch_size=batch_size,
        )

        predictions = None

        # Try SDK path first (only once to determine availability)
        if self._use_sdk is not False:
            try:
                predictions = self._try_sdk_generate(
                    body, project=project, location=location, model=model,
                )
                self._use_sdk = True
            except (ImportError, Exception):
                self._use_sdk = False

        # Fallback to REST
        if predictions is None:
            predictions = self._rest_generate(
                body, project=project, location=location, model=model,
            )

        # Decode first prediction (base64-encoded WAV)
        audio_bytes = None
        if predictions:
            encoded = predictions[0]
            if isinstance(encoded, dict):
                encoded = encoded.get("bytesBase64Encoded", encoded.get("audio", ""))
            if isinstance(encoded, str):
                audio_bytes = base64.b64decode(encoded)
            elif isinstance(encoded, bytes):
                audio_bytes = encoded

        return Song(
            audio=AudioResult(
                audio_bytes=audio_bytes,
                format="wav",
                sample_rate=_SAMPLE_RATE,
                duration_seconds=_FIXED_DURATION,
            ),
            platform="lyria2",
            status="complete",
            metadata={
                "model": model,
                "batch_size": batch_size,
                "negative_prompt": negative_prompt,
            },
        )
