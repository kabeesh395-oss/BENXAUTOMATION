"""Tests for language registry."""

import pytest

from benxautomation.i18n.registry import LanguageInfo, LanguageRegistry


class TestLanguageRegistry:
    def test_seeded_with_english(self):
        reg = LanguageRegistry()
        assert reg.count >= 1
        assert "en" in reg.list_codes()
        en_info = reg.get("en")
        assert en_info is not None
        assert en_info.name == "English"
        assert en_info.rtl is False

    def test_register_new_language(self):
        reg = LanguageRegistry()
        hi = LanguageInfo(code="hi", name="Hindi", native_name="हिन्दी")
        reg.register(hi)

        assert "hi" in reg.list_codes()
        assert reg.get("hi") == hi

    def test_get_nonexistent_returns_none(self):
        reg = LanguageRegistry()
        assert reg.get("nonexistent") is None

    def test_list_all_sorted_by_code(self):
        reg = LanguageRegistry()
        reg.register(LanguageInfo(code="fr", name="French", native_name="Français"))
        reg.register(LanguageInfo(code="de", name="German", native_name="Deutsch"))

        codes = [item.code for item in reg.list_all()]
        assert codes == sorted(codes)
