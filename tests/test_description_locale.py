"""PT-PT description fallback must be deterministic and metadata-only."""
import unittest
from copy import deepcopy

from scripts.description_locale import enrich


class DescriptionLocaleTests(unittest.TestCase):
    def test_fills_missing_pt_from_app_specific_curated_text(self):
        meta = {"description": {"en_US": "Manage your personal expenses."},
                "icon": "https://example.com/icon.png"}
        before_icon = meta["icon"]
        self.assertTrue(enrich(meta, "Gestão de orçamento e despesas pessoais"))
        self.assertIn("Gestão de orçamento e despesas pessoais", meta["description"]["pt_PT"])
        self.assertEqual("Manage your personal expenses.", meta["description"]["en_US"])
        self.assertEqual(before_icon, meta["icon"])

    def test_preserves_human_curated_pt(self):
        meta = {"description": {"en_US": "Manage personal expenses",
                                "pt_PT": "Descrição portuguesa completa e específica."}}
        before = deepcopy(meta)
        self.assertFalse(enrich(meta, "Resumo"))
        self.assertEqual(before, meta)

    def test_missing_english_or_empty_curated_subtitle_is_rejected(self):
        with self.assertRaises(ValueError):
            enrich({"description": {}}, "Resumo")
        with self.assertRaises(ValueError):
            enrich({"description": {"en_US": "Product"}}, "  ")


if __name__ == "__main__":
    unittest.main()
