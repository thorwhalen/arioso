# arioso.named_prompts

Named prompts: a ledger of (name, prompt_text) pairs organized by category.

Provides a system for looking up sonic descriptions by name (artist, mood, genre,
instrument, etc.) to help users craft prompts for AI music generation without using
restricted names.

The system has two layers:

- **Starter data**: ships with arioso in `arioso/data/named_prompts/*.yaml`
- **User data**: stored in `~/.local/share/arioso/named_prompts/*.yaml`

User data overlays starter data, so users can extend or override entries.

Usage:

```default
>>> from arioso.named_prompts import named_prompts, search
>>> named_prompts.artists['billie_eilish']  # attribute access by category
'...'
>>> named_prompts['artists', 'billie_eilish']  # flat key access
'...'
>>> results = search('jazz')  # search across all categories
```

### Functions

| [`add_prompt`](#arioso.named_prompts.add_prompt)(category, name, prompt_text, \*[, ...])   | Add or update a prompt in the user's data.               |
|-------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| [`get_named_prompts`](#arioso.named_prompts.get_named_prompts)()                                  | Return a module-level singleton `NamedPrompts` instance. |
| [`remove_prompt`](#arioso.named_prompts.remove_prompt)(category, name)                        | Remove a prompt from the user's data.                    |
| [`search`](#arioso.named_prompts.search)(query, \*[, categories, ...])                 | Search for prompts matching a query string.              |

### Classes

| [`NamedPrompts`](#arioso.named_prompts.NamedPrompts)(\*[, include_user_data])   | Two-level mapping of `(category, name) -> prompt_text`.   |
|------------------------------------------------------------------------------------------|-----------------------------------------------------------|

### *class* arioso.named_prompts.NamedPrompts(, include_user_data=True)

Bases: [`Mapping`](https://docs.python.org/3/library/typing.html#typing.Mapping)

Two-level mapping of `(category, name) -> prompt_text`.

Supports both hierarchical and flat access:

```default
np = NamedPrompts()
np.artists['billie_eilish']     # attribute access to a category
np['artists']['billie_eilish']  # dict-style
np['artists', 'billie_eilish']  # flat tuple key
```

Categories are auto-discovered from YAML files in the starter and user dirs.

* **Parameters:**
  **include_user_data** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to layer user data on top of starter data.
  Defaults to `True`.

#### *property* categories *: [Tuple](https://docs.python.org/3/library/typing.html#typing.Tuple)[[str](https://docs.python.org/3/library/stdtypes.html#str), ...]*

Return all available category names.

#### flat()

Return a flat dict of `{(category, name): prompt_text}`.

* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)], [`str`](https://docs.python.org/3/library/stdtypes.html#str)]

#### flat_names(, warn_collisions=True)

Return a flat dict of `{name: prompt_text}`, ignoring categories.

If the same name appears in multiple categories, the last one wins
and a warning is issued (unless `warn_collisions=False`).

* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)]

### arioso.named_prompts.add_prompt(category, name, prompt_text, , confirm_override=True)

Add or update a prompt in the user’s data.

If the name already exists in either user or starter data and
`confirm_override` is True, a confirmation prompt is printed on the
first collision.

* **Parameters:**
  * **category** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – The category to add to (e.g. ‘artists’, ‘moods’).
  * **name** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – The identifier for this prompt.
  * **prompt_text** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – The sonic description / prompt text.
  * **confirm_override** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If True, warn when overriding an existing entry.
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)

### arioso.named_prompts.get_named_prompts()

Return a module-level singleton `NamedPrompts` instance.

* **Return type:**
  [`NamedPrompts`](#arioso.named_prompts.NamedPrompts)

### arioso.named_prompts.remove_prompt(category, name)

Remove a prompt from the user’s data.

This only removes from user data. Starter data entries cannot be removed
(but can be overridden via `add_prompt`).

* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)

### arioso.named_prompts.search(query, , categories=None, search_prompts=True, search_names=True)

Search for prompts matching a query string.

* **Parameters:**
  * **query** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Case-insensitive substring to search for.
  * **categories** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)]]) – If given, restrict search to these categories.
  * **search_prompts** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to search in prompt text.
  * **search_names** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to search in entry names.
* **Return type:**
  [`Dict`](https://docs.python.org/3/library/typing.html#typing.Dict)[[`Tuple`](https://docs.python.org/3/library/typing.html#typing.Tuple)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)], [`str`](https://docs.python.org/3/library/stdtypes.html#str)]
* **Returns:**
  Dict of `{(category, name): prompt_text}` for all matches.
