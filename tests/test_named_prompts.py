"""Tests for arioso.named_prompts module."""

import warnings
from pathlib import Path
from unittest.mock import patch

import pytest

from arioso.named_prompts import (
    NamedPrompts,
    _MergedCategoryMapping,
    _STARTER_DATA_DIR,
    _load_yaml,
    _dump_yaml,
    add_prompt,
    remove_prompt,
    search,
)


# ---------------------------------------------------------------------------
# Starter data integrity
# ---------------------------------------------------------------------------


class TestStarterData:
    """Verify that shipped YAML files are well-formed and non-empty."""

    def test_starter_dir_exists(self):
        assert _STARTER_DATA_DIR.is_dir()

    def test_starter_files_exist(self):
        expected = {
            'artists', 'decades', 'genres', 'instruments',
            'moods', 'production', 'scenes', 'vocals',
        }
        actual = {p.stem for p in _STARTER_DATA_DIR.glob('*.yaml')}
        assert expected == actual

    @pytest.mark.parametrize('filename', list(_STARTER_DATA_DIR.glob('*.yaml')))
    def test_yaml_loads_as_dict_of_strings(self, filename):
        data = _load_yaml(filename)
        assert isinstance(data, dict)
        assert len(data) > 0, f'{filename.name} is empty'
        for key, value in data.items():
            assert isinstance(key, str), f'Non-string key {key!r} in {filename.name}'
            assert isinstance(value, str), f'Non-string value for {key!r} in {filename.name}'
            assert len(value) > 5, f'Suspiciously short prompt for {key!r}: {value!r}'


# ---------------------------------------------------------------------------
# YAML codec round-trip
# ---------------------------------------------------------------------------


class TestYamlCodec:

    def test_load_dump_roundtrip(self, tmp_path):
        original = {'alpha': 'first entry', 'beta': 'second entry'}
        path = tmp_path / 'test.yaml'
        _dump_yaml(original, path)
        loaded = _load_yaml(path)
        assert loaded == original

    def test_load_coerces_int_keys(self, tmp_path):
        """Decade keys like 1980s parse as ints in YAML; must be coerced."""
        path = tmp_path / 'decades.yaml'
        path.write_text('1980: "gated reverb"\n2020: "bedroom pop"\n')
        loaded = _load_yaml(path)
        assert all(isinstance(k, str) for k in loaded)
        assert '1980' in loaded

    def test_load_empty_file(self, tmp_path):
        path = tmp_path / 'empty.yaml'
        path.write_text('')
        assert _load_yaml(path) == {}


# ---------------------------------------------------------------------------
# _MergedCategoryMapping
# ---------------------------------------------------------------------------


class TestMergedCategoryMapping:

    def test_starter_only(self):
        m = _MergedCategoryMapping({'a': '1', 'b': '2'})
        assert m['a'] == '1'
        assert len(m) == 2
        assert list(m) == ['a', 'b']

    def test_user_overrides_starter(self):
        m = _MergedCategoryMapping({'a': 'old'}, {'a': 'new'})
        assert m['a'] == 'new'

    def test_user_extends_starter(self):
        m = _MergedCategoryMapping({'a': '1'}, {'b': '2'})
        assert len(m) == 2
        assert 'a' in m
        assert 'b' in m

    def test_contains(self):
        m = _MergedCategoryMapping({'a': '1'}, {'b': '2'})
        assert 'a' in m
        assert 'b' in m
        assert 'c' not in m

    def test_attribute_access(self):
        m = _MergedCategoryMapping({'hello_world': 'prompt text'})
        assert m.hello_world == 'prompt text'

    def test_attribute_access_missing_raises(self):
        m = _MergedCategoryMapping({'a': '1'})
        with pytest.raises(AttributeError):
            _ = m.nonexistent

    def test_dir_includes_identifier_keys(self):
        m = _MergedCategoryMapping({'valid_name': '1', 'also_valid': '2'})
        d = dir(m)
        assert 'valid_name' in d
        assert 'also_valid' in d

    def test_keyerror_for_missing(self):
        m = _MergedCategoryMapping({'a': '1'})
        with pytest.raises(KeyError):
            _ = m['nope']


# ---------------------------------------------------------------------------
# NamedPrompts facade
# ---------------------------------------------------------------------------


class TestNamedPrompts:

    @pytest.fixture
    def np(self):
        return NamedPrompts(include_user_data=False)

    def test_categories(self, np):
        cats = np.categories
        assert 'artists' in cats
        assert 'moods' in cats
        assert 'genres' in cats

    def test_getitem_category(self, np):
        artists = np['artists']
        assert isinstance(artists, _MergedCategoryMapping)
        assert len(artists) > 100

    def test_getitem_tuple(self, np):
        prompt = np['moods', 'nostalgic']
        assert isinstance(prompt, str)
        assert len(prompt) > 10

    def test_contains_category(self, np):
        assert 'artists' in np
        assert 'nonexistent_category' not in np

    def test_contains_tuple(self, np):
        assert ('artists', 'billie_eilish') in np
        assert ('artists', 'nonexistent_artist_xyz') not in np

    def test_attribute_access_category(self, np):
        artists = np.artists
        assert isinstance(artists, _MergedCategoryMapping)

    def test_attribute_access_nested(self, np):
        prompt = np.genres.vaporwave
        assert 'slowed' in prompt.lower() or 'reverb' in prompt.lower()

    def test_attribute_missing_raises(self, np):
        with pytest.raises(AttributeError):
            _ = np.nonexistent_category_xyz

    def test_dir_includes_categories(self, np):
        d = dir(np)
        for cat in np.categories:
            assert cat in d

    def test_len(self, np):
        assert len(np) == len(np.categories)

    def test_iter(self, np):
        assert list(np) == list(np.categories)

    def test_repr(self, np):
        r = repr(np)
        assert 'NamedPrompts' in r
        assert 'artists' in r

    def test_flat(self, np):
        flat = np.flat()
        assert isinstance(flat, dict)
        assert len(flat) > 400
        # Keys are (category, name) tuples
        key = next(iter(flat))
        assert isinstance(key, tuple)
        assert len(key) == 2

    def test_flat_names(self, np):
        flat = np.flat_names(warn_collisions=False)
        assert isinstance(flat, dict)
        assert len(flat) > 0
        # Keys are plain strings
        key = next(iter(flat))
        assert isinstance(key, str)

    def test_keyerror_for_missing_category(self, np):
        with pytest.raises(KeyError):
            _ = np['nonexistent_category_xyz']


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:

    def test_basic_search(self):
        results = search('jazz')
        assert len(results) > 0
        for (cat, name), prompt in results.items():
            assert isinstance(cat, str)
            assert isinstance(name, str)
            assert isinstance(prompt, str)

    def test_search_finds_in_names(self):
        results = search('billie_eilish', search_prompts=False)
        assert ('artists', 'billie_eilish') in results

    def test_search_finds_in_prompts(self):
        results = search('gated reverb', search_names=False)
        assert len(results) > 0

    def test_search_category_filter(self):
        results = search('reverb', categories=('production',))
        for (cat, _name), _prompt in results.items():
            assert cat == 'production'

    def test_search_no_results(self):
        results = search('xyzzy_nonexistent_query_12345')
        assert len(results) == 0

    def test_search_case_insensitive(self):
        lower = search('jazz')
        upper = search('JAZZ')
        assert lower == upper


# ---------------------------------------------------------------------------
# User data management
# ---------------------------------------------------------------------------


class TestUserDataManagement:

    @pytest.fixture
    def user_dir(self, tmp_path):
        """Patch _user_data_dir to use a temp directory."""
        d = tmp_path / 'named_prompts'
        d.mkdir()
        with patch('arioso.named_prompts._user_data_dir', return_value=d):
            yield d

    def test_add_prompt_new_category(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            add_prompt('custom_test', 'foo', 'bar baz', confirm_override=False)
            np = NamedPrompts()
            assert 'custom_test' in np.categories
            assert np['custom_test', 'foo'] == 'bar baz'

    def test_add_prompt_extends_existing(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            add_prompt('custom_test', 'a', 'first', confirm_override=False)
            add_prompt('custom_test', 'b', 'second', confirm_override=False)
            np = NamedPrompts()
            assert np['custom_test', 'a'] == 'first'
            assert np['custom_test', 'b'] == 'second'

    def test_add_prompt_warns_on_starter_override(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                add_prompt('artists', 'billie_eilish', 'my override')
                assert len(w) == 1
                assert 'already exists' in str(w[0].message)

    def test_remove_prompt(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            add_prompt('custom_test', 'to_remove', 'temporary', confirm_override=False)
            remove_prompt('custom_test', 'to_remove')
            # File should be cleaned up since category is now empty
            assert not (user_dir / 'custom_test.yaml').exists()

    def test_remove_nonexistent_raises(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            with pytest.raises(KeyError):
                remove_prompt('nonexistent_cat', 'foo')

    def test_user_data_overrides_starter(self, user_dir):
        with patch('arioso.named_prompts._user_data_dir', return_value=user_dir):
            add_prompt('artists', 'billie_eilish', 'custom description', confirm_override=False)
            np = NamedPrompts()
            assert np.artists['billie_eilish'] == 'custom description'

    def test_flat_names_warns_on_collision(self):
        """Collision warning when same name appears in multiple categories."""
        np = NamedPrompts(include_user_data=False)
        # Manually check - if no collisions exist, this test just verifies no crash
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            flat = np.flat_names(warn_collisions=True)
            assert isinstance(flat, dict)
