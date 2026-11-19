import random
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from loterias import catalog, results, services
from loterias.models import Ticket
from wallet.services import get_wallet

from .test_results import sample


class ScoreTests(SimpleTestCase):
    def test_megasena(self):
        mega = catalog.get("megasena")
        result = results.parse(sample("megasena"))
        outcome = services.score(mega, [5, 19, 22, 44, 1, 2], [], result)
        self.assertEqual(outcome["hits"], 4)
        self.assertEqual(outcome["tiers"], ["4 acertos"])
        self.assertEqual(outcome["payout"], Decimal("709.33"))
        self.assertEqual(services.score(mega, [1, 2, 3, 4, 5, 6], [], result)["tiers"], [])
        alone = services.score(mega, [5, 19, 22, 44, 47, 57], [], result)
        self.assertEqual(alone["tiers"], ["6 acertos"])
        self.assertTrue(alone["jackpot_alone"])
        self.assertEqual(alone["payout"], Decimal("137920959.97"))

    def test_lotomania_zero_hits(self):
        lotomania = catalog.get("lotomania")
        result = results.parse(sample("lotomania"))
        drawn = {int(n) for n in result.numbers}
        none = [n for n in range(100) if n not in drawn][:50]
        self.assertEqual(services.score(lotomania, none, [], result)["tiers"], ["0 acertos"])

    def test_dupla_sena_both_draws(self):
        dupla = catalog.get("duplasena")
        result = results.parse(sample("duplasena"))
        outcome = services.score(dupla, [3, 11, 17, 8, 16, 31], [], result)
        self.assertEqual((outcome["hits"], outcome["second_hits"]), (3, 3))
        self.assertEqual(outcome["tiers"], ["1º sorteio: 3 acertos", "2º sorteio: 3 acertos"])
        self.assertEqual(outcome["payout"], Decimal("3.03") + Decimal("3.25"))

    def test_extras(self):
        dia = catalog.get("diadesorte")
        result = results.parse(sample("diadesorte"))
        outcome = services.score(dia, [2, 4, 9, 10, 1, 3, 5], [1], result)
        self.assertEqual(outcome["tiers"], ["4 acertos", "Mês da Sorte"])
        self.assertEqual(outcome["payout"], Decimal("5.00") + Decimal("2.50"))
        self.assertEqual(services.score(dia, [1, 3, 5, 6, 7, 8, 11], [2], result)["tiers"], [])

        mais = catalog.get("maismilionaria")
        result = results.parse(sample("maismilionaria"))
        outcome = services.score(mais, [6, 15, 1, 2, 3, 4], [3, 6], result)
        self.assertEqual(outcome["tiers"], ["2 acertos + 2 trevos"])
        self.assertEqual(outcome["payout"], Decimal("12.00"))
        self.assertEqual(
            services.score(mais, [6, 15, 28, 30, 1, 2], [1, 2], result)["tiers"], ["4 acertos + 1 ou nenhum trevo"]
        )

        time = catalog.get("timemania")
        result = results.parse(sample("timemania"))
        outcome = services.score(time, [39, 40, 60, 1, 2, 3, 4, 5, 6, 7], [], result)
        self.assertEqual(outcome["tiers"], ["3 acertos"])
        self.assertEqual(outcome["extra_hits"], 0)

    def test_super_sete_columns(self):
        sete = catalog.get("supersete")
        result = results.parse(sample("supersete"))  # 8 7 6 6 0 5 4
        outcome = services.score(sete, [8, 7, 6, 1, 1, 1, 1], [], result)
        self.assertEqual(outcome["hits"], 3)
        self.assertEqual(outcome["payout"], Decimal("6.00"))
        self.assertEqual(services.score(sete, [6, 6, 8, 7, 1, 1, 1], [], result)["hits"], 0)


class PickTests(SimpleTestCase):
    def test_validate(self):
        mega = catalog.get("megasena")
        self.assertEqual(services.validate_pick(mega, ["60", "1", "7", "33", "2", "15"]), ([1, 2, 7, 15, 33, 60], []))
        for bad in (["1", "2", "3", "4", "5"], ["1", "1", "2", "3", "4", "5"], ["0", "1", "2", "3", "4", "5"], ["x"] * 6):
            with self.assertRaises(services.InvalidPick):
                services.validate_pick(mega, bad)
        self.assertEqual(services.validate_pick(catalog.get("lotomania"), range(50)), (list(range(50)), []))
        self.assertEqual(services.validate_pick(catalog.get("supersete"), "8766054"), ([8, 7, 6, 6, 0, 5, 4], []))
        self.assertEqual(services.validate_pick(catalog.get("diadesorte"), range(1, 8), ["12"]), ([1, 2, 3, 4, 5, 6, 7], [12]))
        with self.assertRaises(services.InvalidPick):
            services.validate_pick(catalog.get("diadesorte"), range(1, 8), [])
        with self.assertRaises(services.InvalidPick):
            services.validate_pick(catalog.get("maismilionaria"), range(1, 7), [1, 7])
        self.assertEqual(services.validate_pick(catalog.get("timemania"), range(1, 11), [5]), (list(range(1, 11)), []))
        with self.assertRaises(services.InvalidPick):
            services.validate_pick(catalog.get("federal"), [1])

    def test_surpresinha_is_valid(self):
        rng = random.Random(42)
        for lottery in catalog.playable():
            numbers, extra = services.surpresinha(lottery, rng)
            self.assertEqual(services.validate_pick(lottery, numbers, extra), (numbers, extra))


class TicketTests(TestCase):
    def setUp(self):
        cache.clear()
        today = mock.patch.object(results, "_today", return_value=date(2026, 10, 11))
        today.start()
        self.addCleanup(today.stop)
        self.user = get_user_model().objects.create_user("ana", password="x")
        self.mega = catalog.get("megasena")
        results.store(sample("megasena"))

    def test_place_and_settle(self):
        with mock.patch.object(results, "_download", return_value=sample("megasena")):
            ticket = services.place_ticket(self.user, self.mega, [5, 19, 22, 44, 1, 2])
        self.assertEqual(ticket.contest, 3070)
        self.assertEqual(ticket.stake, Decimal("6.00"))
        wallet = get_wallet(self.user)
        self.assertEqual(wallet.balance, Decimal("994.00"))
        self.assertEqual(wallet.transactions.filter(game="LOTERIA").count(), 1)

        with mock.patch.object(results, "_download") as download:
            self.assertEqual(services.settle_pending(self.user), [], "o concurso 3070 ainda não saiu")
        download.assert_not_called()
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.PENDING)

        drawn = dict(sample("megasena"), numero=3070, numeroConcursoProximo=3071)
        cache.clear()
        results.store(drawn)
        settled = services.settle_pending(self.user)
        self.assertEqual([t.pk for t in settled], [ticket.pk])
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.hits, ticket.tiers), (Ticket.Status.WON, 4, ["4 acertos"]))
        self.assertEqual(ticket.payout, Decimal("709.33"))
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("994.00") + Decimal("709.33"))
        self.assertEqual(ticket.numbers_label, "01 02 05 19 22 44")
        self.assertIn("4 acerto(s)", ticket.hits_label)

    def test_place_requires_results(self):
        from loterias.models import ResultSnapshot

        ResultSnapshot.objects.filter(lottery="megasena").delete()
        with mock.patch.object(results, "_download", side_effect=results.ResultsUnavailable("x")):
            with self.assertRaises(results.ResultsUnavailable):
                services.place_ticket(self.user, self.mega, [1, 2, 3, 4, 5, 6])
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertEqual(get_wallet(self.user).balance, Decimal("1000.00"))

    def test_losing_ticket(self):
        ticket = services.place_ticket(self.user, self.mega, [1, 2, 3, 4, 5, 6], contest=3069)
        self.assertTrue(services.check_ticket(ticket))
        ticket.refresh_from_db()
        self.assertEqual((ticket.status, ticket.payout), (Ticket.Status.LOST, Decimal("0.00")))
        self.assertFalse(services.check_ticket(ticket), "não confere duas vezes")
        self.assertEqual(get_wallet(self.user).balance, Decimal("994.00"))

    def test_settle_is_idempotent(self):
        ticket = Ticket.objects.create(
            user=self.user,
            lottery="megasena",
            contest=3069,
            numbers=[5, 19, 22, 44, 1, 2],
            stake=Decimal("6.00"),
        )
        result = results.known_latest("megasena")
        self.assertIsNotNone(services.settle(ticket, result))
        self.assertIsNone(services.settle(ticket, result))
        wallet = get_wallet(self.user)
        self.assertEqual(wallet.transactions.filter(kind="PAYOUT", game="LOTERIA").count(), 1)
        self.assertEqual(wallet.balance, Decimal("1709.33"))
