from decimal import Decimal
from fractions import Fraction
from math import comb

from django.test import SimpleTestCase

from loterias import catalog, odds


class OddsTests(SimpleTestCase):
    """Valores publicados pela Caixa ("probabilidade de acerto: 1 em N")."""

    KNOWN = {
        "megasena": {"6 acertos": 50_063_860, "5 acertos": 154_518, "4 acertos": 2_332},
        "quina": {"5 acertos": 24_040_016, "4 acertos": 64_106, "3 acertos": 866, "2 acertos": 36},
        "lotofacil": {"15 acertos": 3_268_760, "14 acertos": 21_792, "13 acertos": 692, "12 acertos": 60, "11 acertos": 11},
        "lotomania": {
            "20 acertos": 11_372_635, "19 acertos": 352_551, "18 acertos": 24_235, "17 acertos": 2_776,
            "16 acertos": 472, "15 acertos": 112, "0 acertos": 11_372_635,
        },
        "duplasena": {
            "1º sorteio: 6 acertos": 15_890_700, "1º sorteio: 5 acertos": 60_192,
            "1º sorteio: 4 acertos": 1_120, "2º sorteio: 3 acertos": 60,
        },
        "timemania": {
            "7 acertos": 26_472_637, "6 acertos": 216_103, "5 acertos": 5_220,
            "4 acertos": 276, "3 acertos": 29, "Time do Coração": 80,
        },
        "diadesorte": {"7 acertos": 2_629_575, "6 acertos": 15_652, "5 acertos": 453, "4 acertos": 37, "Mês da Sorte": 12},
        "supersete": {"7 acertos": 10_000_000, "6 acertos": 158_730, "5 acertos": 5_879, "4 acertos": 392},
        "maismilionaria": {"6 acertos + 2 trevos": 238_360_500, "4 acertos + 2 trevos": 16_798, "2 acertos + 1 trevo": 15},
    }

    def test_known_values(self):
        for slug, expected in self.KNOWN.items():
            table = {row["label"]: row for row in odds.odds_table(catalog.get(slug))}
            for label, one_in in expected.items():
                with self.subTest(slug=slug, label=label):
                    self.assertIn(label, table)
                    self.assertAlmostEqual(table[label]["one_in"], one_in, delta=max(1, one_in * 0.0005))

    def test_exact_fractions(self):
        mega = catalog.get("megasena")
        self.assertEqual(odds.main_probability(mega, 6), Fraction(1, 50_063_860))
        self.assertEqual(odds.hypergeometric(60, 6, 6, 7), Fraction(0))
        self.assertEqual(odds.binomial(7, 7), Fraction(1, 10_000_000))
        self.assertEqual(odds.extra_probability(catalog.get("diadesorte"), 1), Fraction(1, 12))
        self.assertEqual(odds.extra_probability(mega, 0), Fraction(1))

    def test_super_sete_three_hits(self):
        row = {r["label"]: r for r in odds.odds_table(catalog.get("supersete"))}["3 acertos"]
        self.assertAlmostEqual(row["one_in"], 43.55, places=1)

    def test_any_prize_and_combinations(self):
        lotofacil = catalog.get("lotofacil")
        self.assertGreater(odds.any_prize_probability(lotofacil), Fraction(1, 12))
        self.assertLess(odds.any_prize_probability(catalog.get("megasena")), Fraction(1, 2000))
        self.assertEqual(odds.total_combinations(catalog.get("megasena")), 50_063_860)
        self.assertEqual(odds.total_combinations(catalog.get("maismilionaria")), 238_360_500)
        self.assertEqual(odds.total_combinations(catalog.get("supersete")), 10_000_000)
        self.assertEqual(odds.total_combinations(catalog.get("timemania")), comb(80, 10))


class CatalogTests(SimpleTestCase):
    def test_catalog_shape(self):
        self.assertEqual(len(catalog.LOTTERIES), 11)
        self.assertEqual(len(catalog.playable()), 9)
        lotomania = catalog.get("lotomania")
        self.assertEqual((lotomania.first, lotomania.last, lotomania.digits), (0, 99, 2))
        self.assertEqual(catalog.get("megasena").digits, 2)
        self.assertEqual(catalog.get("megasena").house_share, Decimal("56.21"))
        for lottery in catalog.LOTTERIES.values():
            with self.subTest(slug=lottery.slug):
                self.assertTrue(lottery.official_url.startswith("https://loterias.caixa.gov.br/"))
                self.assertGreater(lottery.price, 0)
                self.assertTrue(lottery.how_to)
                if lottery.playable:
                    self.assertTrue(lottery.tiers)
        with self.assertRaises(KeyError):
            catalog.get("bingo")

    def test_formatting(self):
        self.assertEqual(catalog.format_numbers(catalog.get("megasena"), [5, 19]), "05 19")
        self.assertEqual(catalog.format_numbers(catalog.get("lotomania"), [0, 7]), "00 07")
        self.assertEqual(catalog.format_numbers(catalog.get("supersete"), [8, 7, 6]), "8 7 6")
        self.assertEqual(catalog.format_extra(catalog.get("diadesorte"), [1]), "Janeiro")
        self.assertEqual(catalog.format_extra(catalog.get("maismilionaria"), [3, 6]), "3 e 6")
        self.assertEqual(catalog.format_extra(catalog.get("megasena"), []), "")
