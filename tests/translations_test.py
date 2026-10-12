import importlib.util
import json
from pathlib import Path
from string import Formatter
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from krest import translations
from krest.translations import T


class TestTranslations(unittest.TestCase):
    def test_import_reads_only_system_language(self):
        spec = importlib.util.spec_from_file_location(
            "krest._translation_test", translations.__file__
        )
        module = importlib.util.module_from_spec(spec)
        with patch("locale.getlocale", return_value=("hu_HU", "UTF-8")):
            with patch.object(Path, "read_text", autospec=True, side_effect=Path.read_text) as read:
                spec.loader.exec_module(module)
        self.assertEqual([call.args[0].name for call in read.call_args_list], ["hu.json"])
        self.assertEqual(module.t(module.t.CLOSE), "Bezárás")

    def test_default_language_is_loaded_on_first_use(self):
        with patch.object(Path, "read_text", autospec=True, side_effect=Path.read_text) as read:
            translator = T()
            read.assert_not_called()
            self.assertEqual(translator(translator.CLOSE), "Close")
            self.assertEqual(translator(translator.CLOSE), "Close")
        self.assertEqual([call.args[0].name for call in read.call_args_list], ["en.json"])

    def test_language_switching_reads_only_selected_catalogs(self):
        translator = T()
        with patch.object(Path, "read_text", autospec=True, side_effect=Path.read_text) as read:
            translator.set_lang("hu-HU")
            self.assertEqual(translator(translator.REPLY_NAME, name="András"), "Örülök a találkozásnak, András!")
            translator.set_lang("hu")
            translator.set_lang("es")
            self.assertEqual(translator(translator.CLOSE), "Cerrar")
            translator.set_lang("en")
            self.assertEqual(translator(translator.CLOSE), "Close")
        self.assertEqual(
            [call.args[0].name for call in read.call_args_list],
            ["hu.json", "es.json", "en.json"],
        )

    def test_missing_or_unsupported_language_falls_back_to_english(self):
        for language in (None, "", "unknown", "xx_YY", "xx-YY", "../../hu"):
            with self.subTest(language=language):
                translator = T()
                translator.set_lang("hu")
                with patch.object(Path, "read_text", autospec=True, side_effect=Path.read_text) as read:
                    translator.set_lang(language)
                self.assertEqual(translator(translator.CLOSE), "Close")
                self.assertEqual([call.args[0].name for call in read.call_args_list], ["en.json"])

    def test_regional_catalog_takes_precedence(self):
        with TemporaryDirectory() as directory:
            locales = Path(directory) / "locales"
            locales.mkdir()
            (locales / "hu_HU.json").write_text('{"CLOSE": "Regional translation"}', encoding="utf-8")
            translator = T()
            with patch.object(translations, "files", return_value=Path(directory)):
                translator.set_lang("hu-HU")
                self.assertEqual(translator(translator.CLOSE), "Regional translation")

    def test_unknown_keys_and_formatting_keep_existing_behavior(self):
        translator = T()
        self.assertEqual(translator("unknown"), "unknown")
        self.assertIsNone(translator(None))
        self.assertEqual(translator(translator.REPLY_NAME), "Nice to meet you, {name}!")
        self.assertEqual(translator(translator.REPLY_NAME, name="User"), "Nice to meet you, User!")
        with self.assertRaises(KeyError):
            translator(translator.REPLY_NAME, unexpected="User")

    def test_missing_english_catalog_reports_error(self):
        with TemporaryDirectory() as directory:
            with patch.object(translations, "files", return_value=Path(directory)):
                with self.assertRaisesRegex(FileNotFoundError, "locales/en.json"):
                    T().set_lang("unknown")

    def test_catalog_keys_values_and_placeholders_are_consistent(self):
        def unique_keys(pairs):
            self.assertEqual(len(pairs), len(dict(pairs)), "Duplicate translation keys")
            return dict(pairs)

        def fields(text):
            return {field for _, field, _, _ in Formatter().parse(text) if field is not None}

        locales = translations.files("krest").joinpath("locales")
        english = json.loads(locales.joinpath("en.json").read_text(encoding="utf-8"))
        expected_keys = {
            name for name, value in vars(T).items()
            if isinstance(value, str) and value.startswith("#TEXT_")
        }
        catalogs = [resource for resource in locales.iterdir() if resource.name.endswith(".json")]
        self.assertTrue(catalogs)
        for resource in catalogs:
            with self.subTest(language=resource.name):
                messages = json.loads(resource.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
                self.assertEqual(set(messages), expected_keys)
                for key, text in messages.items():
                    self.assertIsInstance(text, str)
                    self.assertEqual(fields(text), fields(english[key]), key)


if __name__ == "__main__":
    unittest.main()
