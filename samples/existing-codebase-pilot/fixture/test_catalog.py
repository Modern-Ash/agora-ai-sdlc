import unittest
from decimal import Decimal

from catalog import quote


class QuoteTests(unittest.TestCase):
    def test_single_item(self):
        self.assertEqual(quote("adapter", 1), Decimal("12.50"))

    def test_multiple_items(self):
        self.assertEqual(quote("cable", 3), Decimal("12.00"))

    def test_unknown_sku(self):
        with self.assertRaises(KeyError):
            quote("missing", 1)


if __name__ == "__main__":
    unittest.main()
