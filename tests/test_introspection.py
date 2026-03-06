import pytest
from instagrapi import Client

from ig_cli.introspection import get_method_signature, list_client_methods, summarize_cli_coverage


def test_list_client_methods_contains_public_methods():
    methods = list_client_methods()

    assert "user_info_by_username" in methods
    assert "media_create_livestream" in methods
    assert all(not name.startswith("_") for name in methods)


def test_get_method_signature_returns_parameters():
    signature = get_method_signature("user_info_by_username")

    assert signature["name"] == "user_info_by_username"
    assert any(param["name"] == "username" for param in signature["parameters"])


def test_get_method_signature_rejects_unknown_method_name():
    with pytest.raises(ValueError, match="Unknown client method: not_a_real_method"):
        get_method_signature("not_a_real_method")


def test_get_method_signature_rejects_non_callable_attribute(monkeypatch):
    monkeypatch.setattr(Client, "not_callable_attr", "nope", raising=False)

    with pytest.raises(ValueError, match="Unknown client method: not_callable_attr"):
        get_method_signature("not_callable_attr")


def test_summarize_cli_coverage_reports_missing_methods():
    summary = summarize_cli_coverage(curated_methods={"user_info_by_username"})

    assert "user_info_by_username" in summary["covered"]
    assert "media_create_livestream" in summary["missing"]
    assert summary["covered_count"] == 1
