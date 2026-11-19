import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from loterias import catalog, results
from loterias.models import ResultSnapshot, Ticket

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def sample(slug):
    """Resposta real da API da Caixa, gravada em 11/10/2026."""
    return json.loads((SAMPLES / f"{slug}.json").read_text(encoding="utf-8"))


class ParseTests(SimpleTestCase):
    def test_parse_all_samples(self):
        for slug in catalog.LOTTERIES:
            with self.subTest(slug=slug):
                result = results.parse(sample(slug))
                self.assertEqual(result.lottery, slug)
                self.assertGreater(result.contest, 0)
                self.assertIsNotNone(result.date)
                self.assertTrue(result.numbers or result.matches)

    def test_parse_details(self):
        mega = results.parse(sample("megasena"))
        self.assertEqual(mega.contest, 3069)
        self.assertEqual(mega.numbers, ["05", "19", "22", "44", "47", "57"])
        self.assertEqual(mega.next_contest, 3070)
        self.assertEqual(str(mega.next_date), "2026-10-14")
        self.assertEqual(mega.next_estimate, Decimal("150000000.00"))
        self.assertEqual(mega.jackpot, Decimal("137920959.97"))
        self.assertTrue(mega.accumulated)
        self.assertEqual(mega.tier("5 acertos").winners, 150)
        self.assertEqual(mega.tier("5 acertos").prize, Decimal("26095.23"))
        self.assertEqual(mega.location, "ESPAÇO DA SORTE SÃO PAULO, SP")
        self.assertEqual(mega.extra_values, [], "campo vem com bytes nulos quando não há extra")
        self.assertEqual(results.parse(sample("quina")).extra_values, [])

        dupla = results.parse(sample("duplasena"))
        self.assertEqual(dupla.second_numbers, ["08", "16", "31", "35", "44", "47"])
        self.assertEqual(
            [t.label for t in dupla.tiers][:5],
            ["1º sorteio: 6 acertos", "1º sorteio: 5 acertos", "1º sorteio: 4 acertos", "1º sorteio: 3 acertos", "2º sorteio: 6 acertos"],
        )
        self.assertEqual(results.parse(sample("maismilionaria")).extra_values, ["3", "6"])
        self.assertEqual(results.parse(sample("diadesorte")).extra_values, ["Janeiro"])
        self.assertEqual(results.parse(sample("timemania")).extra_values, ["CONFIANCA SAF /SE"])
        self.assertEqual(results.parse(sample("federal")).numbers[0], "042050")
        loteca = results.parse(sample("loteca"))
        self.assertEqual(len(loteca.matches), 14)
        self.assertEqual(loteca.matches[0]["home"], "PORTUGAL")

    def test_parse_rejects_garbage(self):
        with self.assertRaises(results.ResultsUnavailable):
            results.parse({"exceptionMessage": "erro"})
        with self.assertRaises(results.ResultsUnavailable):
            results.parse({"numero": 1, "tipoJogo": "BINGO"})


class ResultsServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch.object(results, "_today", return_value=date(2026, 10, 11))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_latest_catches_up_when_endpoint_lags(self):
        stale = dict(sample("megasena"), numero=3068, numeroConcursoProximo=3069, dataProximoConcurso="11/10/2026")

        def fake(url):
            return sample("megasena") if url.endswith("/3069") else stale

        with mock.patch.object(results, "_download", side_effect=fake) as download:
            self.assertEqual(results.latest("megasena").contest, 3069)
        self.assertEqual(download.call_count, 2)
        self.assertEqual(ResultSnapshot.objects.filter(lottery="megasena").count(), 1)

    def test_latest_keeps_current_when_next_is_in_the_future(self):
        with mock.patch.object(results, "_download", return_value=sample("megasena")) as download:
            self.assertEqual(results.latest("megasena").contest, 3069)
        self.assertEqual(download.call_count, 1, "próximo concurso é 14/10: não tenta")

    def test_latest_fetches_and_stores(self):
        with mock.patch.object(results, "_download", return_value=sample("quina")) as download:
            first = results.latest("quina")
            second = results.latest("quina")
        # o próximo concurso (7140) é de hoje: tenta pegá-lo, mas o mock devolve o 7139 de novo
        self.assertEqual(download.call_count, 2)
        self.assertTrue(download.call_args_list[1].args[0].endswith("/quina/7140"))
        self.assertEqual(first.contest, 7139)
        self.assertEqual(second.contest, 7139)
        self.assertFalse(first.stale)
        self.assertEqual(ResultSnapshot.objects.get(lottery="quina", contest=7139).payload["numero"], 7139)

    def test_latest_falls_back_to_snapshot_when_api_fails(self):
        results.store(sample("lotofacil"))
        with mock.patch.object(results, "_download", side_effect=results.ResultsUnavailable("fora do ar")) as download:
            found = results.latest("lotofacil")
            again = results.latest("lotofacil")
        self.assertEqual(download.call_count, 1, "a falha fica em cache por um tempo")
        self.assertEqual(found.contest, 3801)
        self.assertTrue(found.stale)
        self.assertTrue(again.stale)

    def test_latest_without_anything(self):
        with mock.patch.object(results, "_download", side_effect=results.ResultsUnavailable("fora do ar")):
            self.assertIsNone(results.latest("supersete"))

    def test_latest_all_mixes_sources(self):
        results.store(sample("quina"))

        def fake(url):
            if "megasena" in url:
                return sample("megasena")
            raise results.ResultsUnavailable(url)

        with mock.patch.object(results, "_download", side_effect=fake):
            found = results.latest_all(["megasena", "quina", "federal"])
        self.assertEqual(found["megasena"].contest, 3069)
        self.assertTrue(found["quina"].stale)
        self.assertIsNone(found["federal"])

    def test_for_contest(self):
        with mock.patch.object(results, "_download", return_value=sample("megasena")) as download:
            self.assertIsNone(results.for_contest("megasena", 3069), "não deve baixar durante uma requisição")
            self.assertIsNone(results.for_contest("megasena", 3070), "ainda não saiu: não consulta a API")
            self.assertEqual(download.call_count, 0)
        results.store(sample("megasena"))
        self.assertEqual(results.for_contest("megasena", 3069).contest, 3069)
        self.assertIsNone(results.for_contest("megasena", 3068), "só usa snapshots do concurso pedido")

    def test_update_command_fetches_missing_pending_ticket_result(self):
        Ticket.objects.create(
            user=get_user_model().objects.create_user("ana"),
            lottery="megasena",
            contest=3068,
            numbers=[1, 2, 3, 4, 5, 6],
            stake=Decimal("6.00"),
        )

        def fake_download(url):
            payload = sample("megasena")
            if url.endswith("/3068"):
                return dict(payload, numero=3068)
            return payload

        with mock.patch.object(results, "_download", side_effect=fake_download) as download:
            call_command("atualizar_loterias", "megasena", stdout=StringIO())

        self.assertEqual(download.call_count, 2)
        self.assertTrue(ResultSnapshot.objects.filter(lottery="megasena", contest=3068).exists())
