import unittest

from bot.i18n import t
from bot.premium_emoji import PREMIUM_EMOJI, pemoji


class PremiumEmojiTests(unittest.TestCase):
    def test_catalog_ids_are_rendered_with_valid_fallbacks(self):
        for key, (emoji_id, fallback) in PREMIUM_EMOJI.items():
            with self.subTest(key=key):
                tag = pemoji(key)
                self.assertIn(f'emoji-id="{emoji_id}"', tag)
                self.assertIn(f">{fallback}</tg-emoji>", tag)

    def test_compact_reports_use_custom_emoji_entities(self):
        values = {
            "crop": "Пшеница",
            "area_ha": "1",
            "irrigation": "Капельный",
            "temp": "25.0",
            "wind": "2.0",
            "moisture": "0.200",
            "volume_m3": "10",
            "savings": "100",
            "decision": "Норма",
        }
        report = t("ru", "compact_report", **values)
        self.assertIn('emoji-id="5231200819986047254"', report)
        self.assertIn('emoji-id="5391032818111363540"', report)
        self.assertIn('emoji-id="5449683594425410231"', report)


if __name__ == "__main__":
    unittest.main()
