"""Parameter translation layer.

Translates between the 40 unified affordance names and each platform's
native parameter names, applying type coercions along the way.
"""

import warnings
from collections.abc import Callable


def make_kwargs_trans(
    param_map: dict, *, on_unsupported: str = "warn"
) -> Callable[[dict], dict]:
    """Build a kwargs translation function from a platform's param_map.

    The returned function transforms::

        {common_name: value, ...}  ->  {native_name: coerced_value, ...}

    Args:
        param_map: Dict mapping common affordance names to native config
            dicts.  Each value has keys: ``native_name`` (str),
            ``coerce`` (optional callable), ``adapter_handled`` (optional
            bool).
        on_unsupported: What to do with params not in param_map.
            One of 'warn', 'raise', or 'ignore'.

    Returns:
        A function that translates outer kwargs to inner kwargs.
    """

    def kwargs_trans(outer_kwargs: dict) -> dict:
        inner_kwargs = {}
        for common_name, value in outer_kwargs.items():
            if common_name in param_map:
                mapping = param_map[common_name]
                if mapping.get("adapter_handled", False):
                    inner_kwargs[common_name] = value
                    continue
                native_name = mapping.get("native_name", common_name)
                if native_name is None:
                    continue
                coerce = mapping.get("coerce")
                if coerce is not None:
                    value = coerce(value)
                inner_kwargs[native_name] = value
            else:
                if on_unsupported == "raise":
                    raise ValueError(
                        f"Parameter {common_name!r} not supported by this platform"
                    )
                elif on_unsupported == "warn":
                    warnings.warn(
                        f"Parameter {common_name!r} not supported, ignoring",
                        stacklevel=2,
                    )
                # 'ignore': silently drop
        return inner_kwargs

    return kwargs_trans


def make_generate_func(config: dict) -> Callable:
    """Build a generate() callable from a platform config.

    This is the fallback when no custom adapter.py is provided.
    For REST API platforms, it builds the HTTP function from the config
    and wraps it with parameter translation and output normalization.

    Args:
        config: A PLATFORM_CONFIG dict.

    Returns:
        A callable that accepts unified affordance kwargs and returns
        a Song.
    """
    param_map = config.get("param_map", {})
    on_unsupported = config.get("on_unsupported_param", "warn")
    kwargs_trans_fn = make_kwargs_trans(param_map, on_unsupported=on_unsupported)

    access_type = config.get("access_type", "rest_api")

    if access_type == "rest_api":
        raw_func = _build_rest_func(config)
    elif access_type == "python_lib":
        raise NotImplementedError(
            f"Platform {config.get('name', '?')!r} requires an adapter.py "
            f"for python_lib access"
        )
    else:
        raise NotImplementedError(f"Access type {access_type!r} not yet supported")

    egress = _build_egress(config)

    def generate(prompt: str, **kwargs):
        all_kwargs = {"prompt": prompt, **kwargs}
        native_kwargs = kwargs_trans_fn(all_kwargs)
        raw_result = raw_func(**native_kwargs)
        return egress(raw_result)

    generate.__name__ = "generate"
    generate.__qualname__ = f"{config.get('name', 'unknown')}.generate"
    return generate


def _build_rest_func(config: dict) -> Callable:
    """Build the raw HTTP callable for a REST API platform.

    If an OpenAPI spec URL is in the config, uses ``ho.route_to_func``
    to auto-generate it. Otherwise, builds a simple requests-based
    function from the endpoint config.
    """
    api_config = config.get("api", {})
    openapi_url = api_config.get("openapi_spec_url")
    auth_config = config.get("auth", {})

    if openapi_url:
        from ho import route_to_func
        from ju.oas import Routes, ensure_openapi_dict

        from arioso._util import build_auth_headers

        spec = ensure_openapi_dict(openapi_url)
        routes = Routes(spec)

        endpoint = api_config.get("generate_endpoint", {})
        method = endpoint.get("method", "post")
        path = endpoint.get("path", "")

        target_route = routes[method, path]
        headers = build_auth_headers(auth_config)

        return route_to_func(
            target_route,
            api_config["base_url"],
            custom_headers=headers,
        )
    else:
        # Simple requests-based function
        from arioso._util import make_session

        base_url = api_config.get("base_url", "")
        endpoint = api_config.get("generate_endpoint", {})
        method = endpoint.get("method", "post")
        path = endpoint.get("path", "/generate")
        url = f"{base_url}{path}"

        session = make_session(auth_config)

        def rest_func(**kwargs):
            resp = getattr(session, method)(url, json=kwargs)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                return resp.json()
            return resp.content

        return rest_func


def _build_egress(config: dict) -> Callable:
    """Build an egress function that normalizes platform output to Song."""
    from arioso.base import AudioResult, Song

    output_config = config.get("output", {})
    returns = output_config.get("returns", "bytes")
    default_format = output_config.get("default_format", "")
    sample_rate = output_config.get("sample_rate", 0)
    platform_name = config.get("name", "")

    def egress(response) -> Song:
        if returns == "bytes":
            if isinstance(response, bytes):
                audio = AudioResult(audio_bytes=response, format=default_format)
            elif isinstance(response, dict):
                audio = AudioResult(
                    audio_url=response.get("audio_url", response.get("url", "")),
                    format=default_format,
                )
            else:
                raw = (
                    response.content
                    if hasattr(response, "content")
                    else bytes(response)
                )
                audio = AudioResult(audio_bytes=raw, format=default_format)
            return Song(audio=audio, platform=platform_name, status="complete")
        elif returns == "url":
            url = (
                response if isinstance(response, str) else response.get("audio_url", "")
            )
            audio = AudioResult(audio_url=url, format=default_format)
            return Song(audio=audio, platform=platform_name, status="complete")
        elif returns == "array":
            audio = AudioResult(
                audio_array=response,
                sample_rate=sample_rate,
                format="wav",
            )
            return Song(audio=audio, platform=platform_name, status="complete")
        return Song(platform=platform_name, status="complete")

    return egress
