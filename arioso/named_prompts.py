"""Named prompts: a ledger of (name, prompt_text) pairs organized by category.

Provides a system for looking up sonic descriptions by name (artist, mood, genre,
instrument, etc.) to help users craft prompts for AI music generation without using
restricted names.

The system has two layers:
- **Starter data**: ships with arioso in ``arioso/data/named_prompts/*.yaml``
- **User data**: stored in ``~/.local/share/arioso/named_prompts/*.yaml``

User data overlays starter data, so users can extend or override entries.

Usage::

    >>> from arioso.named_prompts import named_prompts, search
    >>> named_prompts.artists['billie_eilish']  # attribute access by category
    '...'
    >>> named_prompts['artists', 'billie_eilish']  # flat key access
    '...'
    >>> results = search('jazz')  # search across all categories

"""

import os
import warnings
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_STARTER_DATA_DIR = Path(__file__).parent / "data" / "named_prompts"


def _user_data_dir(*, ensure_exists: bool = True) -> Path:
    """Return the user data directory for named prompts."""
    from config2py import get_app_data_folder

    folder = (
        Path(get_app_data_folder("arioso", ensure_exists=ensure_exists))
        / "named_prompts"
    )
    if ensure_exists:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


# ---------------------------------------------------------------------------
# YAML codec helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Dict[str, str]:
    """Load a YAML file as a dict of {name: prompt_text}."""
    import yaml

    with open(path) as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    # Coerce all keys to strings (decades like 1980s parse as ints in YAML)
    return {str(k): str(v) for k, v in data.items()}


def _dump_yaml(data: Dict[str, str], path: Path) -> None:
    """Write a dict of {name: prompt_text} to a YAML file."""
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.dump(
            data,
            fh,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=True,
        )


# ---------------------------------------------------------------------------
# Store layer (dol-based)
# ---------------------------------------------------------------------------


def _make_yaml_store(root_dir: Path, *, writable: bool = False):
    """Create a dol store that maps ``category`` keys to ``{name: prompt}`` dicts.

    The store reads/writes YAML files in *root_dir*, one file per category.
    Keys are category names (without ``.yaml`` extension); values are dicts.
    """
    from dol import wrap_kvs, TextFiles

    base_cls = TextFiles

    store_cls = wrap_kvs(
        base_cls,
        name="YamlPromptStore",
        # key transform: 'artists' <-> 'artists.yaml'
        key_of_id=lambda _id: _id.removesuffix(".yaml"),
        id_of_key=lambda k: k if k.endswith(".yaml") else f"{k}.yaml",
        # value transform: YAML text <-> dict
        obj_of_data=lambda data: _yaml_text_to_dict(data),
        data_of_obj=lambda obj: _dict_to_yaml_text(obj),
    )

    store = store_cls(str(root_dir))

    if not writable:
        # Return a read-only view
        return _ReadOnlyMapping(store)
    return store


def _yaml_text_to_dict(text: str) -> Dict[str, str]:
    import yaml

    data = yaml.safe_load(text)
    if data is None:
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _dict_to_yaml_text(d: Dict[str, str]) -> str:
    import yaml

    return yaml.dump(
        d,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=True,
    )


class _ReadOnlyMapping(Mapping):
    """A thin read-only wrapper around a mutable mapping."""

    __slots__ = ("_store",)

    def __init__(self, store):
        self._store = store

    def __getitem__(self, key):
        return self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return f"{type(self).__name__}({list(self)})"


# ---------------------------------------------------------------------------
# Merged view: starter + user
# ---------------------------------------------------------------------------


class _MergedCategoryMapping(Mapping):
    """A read-only view of a single category that merges starter and user dicts.

    User entries take precedence over starter entries.
    """

    __slots__ = ("_starter", "_user")

    def __init__(
        self,
        starter: Dict[str, str],
        user: Optional[Dict[str, str]] = None,
    ):
        self._starter = starter
        self._user = user or {}

    def __getitem__(self, key: str) -> str:
        if key in self._user:
            return self._user[key]
        return self._starter[key]

    def __iter__(self) -> Iterator[str]:
        seen = set()
        for k in self._user:
            seen.add(k)
            yield k
        for k in self._starter:
            if k not in seen:
                yield k

    def __len__(self) -> int:
        return len(set(self._starter) | set(self._user))

    def __contains__(self, key) -> bool:
        return key in self._user or key in self._starter

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"No prompt named {name!r} in this category")

    def __dir__(self):
        return list(super().__dir__()) + [k for k in self if k.isidentifier()]

    def __repr__(self) -> str:
        n = len(self)
        return f"PromptCategory({n} entries)"


# ---------------------------------------------------------------------------
# Main facade: NamedPrompts
# ---------------------------------------------------------------------------


class NamedPrompts(Mapping):
    """Two-level mapping of ``(category, name) -> prompt_text``.

    Supports both hierarchical and flat access::

        np = NamedPrompts()
        np.artists['billie_eilish']     # attribute access to a category
        np['artists']['billie_eilish']  # dict-style
        np['artists', 'billie_eilish']  # flat tuple key

    Categories are auto-discovered from YAML files in the starter and user dirs.

    Args:
        include_user_data: Whether to layer user data on top of starter data.
            Defaults to ``True``.
    """

    def __init__(self, *, include_user_data: bool = True):
        self._starter_store = _make_yaml_store(_STARTER_DATA_DIR, writable=False)
        self._user_store = None
        if include_user_data:
            user_dir = _user_data_dir(ensure_exists=False)
            if user_dir.exists():
                self._user_store = _make_yaml_store(user_dir, writable=False)
        self._cache: Dict[str, _MergedCategoryMapping] = {}

    # -- Category access ---------------------------------------------------

    def _get_category(self, category: str) -> _MergedCategoryMapping:
        if category not in self._cache:
            starter = (
                self._starter_store[category] if category in self._starter_store else {}
            )
            user = {}
            if self._user_store is not None and category in self._user_store:
                user = self._user_store[category]
            if not starter and not user:
                raise KeyError(category)
            self._cache[category] = _MergedCategoryMapping(starter, user)
        return self._cache[category]

    @property
    def categories(self) -> Tuple[str, ...]:
        """Return all available category names."""
        cats = set(self._starter_store)
        if self._user_store is not None:
            cats |= set(self._user_store)
        return tuple(sorted(cats))

    # -- Mapping interface -------------------------------------------------

    def __getitem__(self, key):
        """Get a category dict or a specific prompt.

        ``np['artists']`` returns the merged category mapping.
        ``np['artists', 'billie_eilish']`` returns the prompt string.
        """
        if isinstance(key, tuple):
            category, name = key
            return self._get_category(category)[name]
        return self._get_category(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.categories)

    def __len__(self) -> int:
        return len(self.categories)

    def __contains__(self, key) -> bool:
        if isinstance(key, tuple):
            category, name = key
            try:
                cat = self._get_category(category)
            except KeyError:
                return False
            return name in cat
        try:
            self._get_category(key)
            return True
        except KeyError:
            return False

    # -- Attribute access (for tab-completion) -----------------------------

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._get_category(name)
        except KeyError:
            raise AttributeError(
                f"{type(self).__name__!r} has no category {name!r}. "
                f"Available: {self.categories}"
            )

    def __dir__(self):
        return list(super().__dir__()) + list(self.categories)

    # -- Flat view ---------------------------------------------------------

    def flat(self) -> Dict[Tuple[str, str], str]:
        """Return a flat dict of ``{(category, name): prompt_text}``."""
        result = {}
        for cat in self.categories:
            for name, prompt in self._get_category(cat).items():
                result[(cat, name)] = prompt
        return result

    def flat_names(self, *, warn_collisions: bool = True) -> Dict[str, str]:
        """Return a flat dict of ``{name: prompt_text}``, ignoring categories.

        If the same name appears in multiple categories, the last one wins
        and a warning is issued (unless ``warn_collisions=False``).
        """
        result: Dict[str, str] = {}
        seen_in: Dict[str, str] = {}  # name -> first category
        for cat in self.categories:
            for name, prompt in self._get_category(cat).items():
                if name in result and warn_collisions and seen_in[name] != cat:
                    warnings.warn(
                        f"Name {name!r} appears in both {seen_in[name]!r} "
                        f"and {cat!r}; using the one from {cat!r}.",
                        stacklevel=2,
                    )
                seen_in.setdefault(name, cat)
                result[name] = prompt
        return result

    # -- Display -----------------------------------------------------------

    def __repr__(self) -> str:
        cats = ", ".join(f"{c}({len(self._get_category(c))})" for c in self.categories)
        return f"NamedPrompts({cats})"


# ---------------------------------------------------------------------------
# User data management
# ---------------------------------------------------------------------------


def add_prompt(
    category: str,
    name: str,
    prompt_text: str,
    *,
    confirm_override: bool = True,
) -> None:
    """Add or update a prompt in the user's data.

    If the name already exists in either user or starter data and
    ``confirm_override`` is True, a confirmation prompt is printed on the
    first collision.

    Args:
        category: The category to add to (e.g. 'artists', 'moods').
        name: The identifier for this prompt.
        prompt_text: The sonic description / prompt text.
        confirm_override: If True, warn when overriding an existing entry.
    """
    user_dir = _user_data_dir(ensure_exists=True)
    user_store = _make_yaml_store(user_dir, writable=True)

    # Load existing user data for this category (or start fresh)
    if category in user_store:
        cat_data = dict(user_store[category])
    else:
        cat_data = {}

    # Check for collision with starter data
    if confirm_override and name not in cat_data:
        starter_store = _make_yaml_store(_STARTER_DATA_DIR, writable=False)
        if category in starter_store:
            starter_data = starter_store[category]
            if name in starter_data:
                warnings.warn(
                    f"{name!r} already exists in starter data for {category!r}. "
                    f"Your entry will take precedence over the built-in one.",
                    stacklevel=2,
                )

    cat_data[name] = prompt_text
    user_store[category] = cat_data


def remove_prompt(category: str, name: str) -> None:
    """Remove a prompt from the user's data.

    This only removes from user data. Starter data entries cannot be removed
    (but can be overridden via ``add_prompt``).
    """
    user_dir = _user_data_dir(ensure_exists=False)
    if not user_dir.exists():
        raise KeyError(f"No user data exists for category {category!r}")

    user_store = _make_yaml_store(user_dir, writable=True)
    if category not in user_store:
        raise KeyError(f"No user data for category {category!r}")

    cat_data = dict(user_store[category])
    if name not in cat_data:
        raise KeyError(f"{name!r} not found in user data for {category!r}")

    del cat_data[name]
    if cat_data:
        user_store[category] = cat_data
    else:
        # Remove the empty file
        yaml_path = user_dir / f"{category}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search(
    query: str,
    *,
    categories: Optional[Tuple[str, ...]] = None,
    search_prompts: bool = True,
    search_names: bool = True,
) -> Dict[Tuple[str, str], str]:
    """Search for prompts matching a query string.

    Args:
        query: Case-insensitive substring to search for.
        categories: If given, restrict search to these categories.
        search_prompts: Whether to search in prompt text.
        search_names: Whether to search in entry names.

    Returns:
        Dict of ``{(category, name): prompt_text}`` for all matches.
    """
    np = NamedPrompts()
    query_lower = query.lower()
    results = {}

    cats = categories if categories is not None else np.categories

    for cat in cats:
        if cat not in np:
            continue
        for name, prompt in np[cat].items():
            match = False
            if search_names and query_lower in name.lower():
                match = True
            if search_prompts and query_lower in prompt.lower():
                match = True
            if match:
                results[(cat, name)] = prompt

    return results


# ---------------------------------------------------------------------------
# Module-level singleton (lazy)
# ---------------------------------------------------------------------------

_named_prompts = None


def get_named_prompts() -> NamedPrompts:
    """Return a module-level singleton ``NamedPrompts`` instance."""
    global _named_prompts
    if _named_prompts is None:
        _named_prompts = NamedPrompts()
    return _named_prompts


# Lazy attribute for ``from arioso.named_prompts import named_prompts``
def __getattr__(name: str):
    if name == "named_prompts":
        return get_named_prompts()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
