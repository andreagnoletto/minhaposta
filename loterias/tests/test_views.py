from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from loterias import catalog, results
from loterias.models import Ticket
from wallet.services import get_wallet

from .test_results import sample


def fake_download(url):
    for slug in catalog.LOTTERIES:
        if f"/api/{slug}" in url:
            return sample(slug)
    raise results.ResultsUnavailable(url)


class PagesTests(TestCase):
    def setUp(self):
        cache.clear()
        today = mock.patch.object(results, "_today", return_value=date(2026, 10, 11))
        today.start()
        self.addCleanup(today.stop)
        patcher = mock.patch.object(results, "_download", side_effect=fake_download)
        self.download = patcher.start()
        self.addCleanup(patcher.stop)
        for slug in catalog.LOTTERIES:
            results.store(sample(slug))

    def test_index_lists_every_lottery_with_results(self):
        response = self.client.get(reverse("loterias:index"))
        self.assertEqual(response.status_code, 200)
        for lottery in catalog.LOTTERIES.values():
            self.assertContains(response, lottery.name)
        self.assertContains(response, "3069")  # concurso da Mega-Sena
        self.assertContains(response, "1 em 50.063.860")
        self.assertContains(response, "PORTUGAL")  # Loteca mostra os jogos

    def test_index_without_api(self):
        from loterias.models import ResultSnapshot

        ResultSnapshot.objects.all().delete()
        self.download.side_effect = results.ResultsUnavailable("fora do ar")
        response = self.client.get(reverse("loterias:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultado indisponível")
        self.download.assert_not_called()

    def test_detail_pages(self):
        for slug in catalog.LOTTERIES:
            with self.subTest(slug=slug):
                response = self.client.get(reverse("loterias:detail", args=[slug]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Último resultado")
        self.download.assert_not_called()
        response = self.client.get(reverse("loterias:detail", args=["megasena"]))
        self.assertContains(response, "1 em 154.518")
        self.assertContains(response, "R$ 300.383.160,00")  # 50.063.860 apostas × R$ 6
        self.assertContains(response, "R$ 26.095,23")  # rateio real da quina
        self.assertContains(response, 'name="n"')
        self.assertContains(response, "Entre para registrar um bilhete")
        self.assertEqual(self.client.get(reverse("loterias:detail", args=["bingo"])).status_code, 404)

    def test_legal_page(self):
        response = self.client.get(reverse("loterias:legal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "loteriasonline.caixa.gov.br")
        self.assertContains(response, "18 anos")

    def test_quick_check_without_login(self):
        url = reverse("loterias:detail", args=["megasena"])
        data = {"acao": "conferir", "n": ["5", "19", "22", "44", "1", "2"]}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "4 acertos")
        self.assertContains(response, "R$ 709,33")
        self.assertEqual(Ticket.objects.count(), 0)

    def test_invalid_pick_shows_error(self):
        url = reverse("loterias:detail", args=["megasena"])
        response = self.client.post(url, {"acao": "conferir", "n": ["5", "19"]})
        self.assertContains(response, "Marque exatamente 6 números")

    def test_register_requires_login(self):
        url = reverse("loterias:detail", args=["quina"])
        response = self.client.post(url, {"acao": "registrar", "n": ["1", "2", "3", "4", "5"]})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


class TicketViewTests(TestCase):
    def setUp(self):
        cache.clear()
        today = mock.patch.object(results, "_today", return_value=date(2026, 10, 11))
        today.start()
        self.addCleanup(today.stop)
        patcher = mock.patch.object(results, "_download", side_effect=fake_download)
        self.download = patcher.start()
        self.addCleanup(patcher.stop)
        for slug in catalog.LOTTERIES:
            results.store(sample(slug))
        self.user = get_user_model().objects.create_user("bia", password="x")
        self.client.force_login(self.user)

    def test_register_ticket(self):
        url = reverse("loterias:detail", args=["diadesorte"])
        data = {"acao": "registrar", "n": ["2", "4", "9", "10", "1", "3", "5"], "extra": "1"}
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, url)
        self.assertContains(response, "Bilhete de treino registrado")
        ticket = Ticket.objects.get()
        self.assertEqual((ticket.lottery, ticket.contest, ticket.extra), ("diadesorte", 1320, [1]))
        self.assertEqual(ticket.numbers, [1, 2, 3, 4, 5, 9, 10])
        self.assertEqual(get_wallet(self.user).balance, Decimal("997.50"))
        self.assertContains(response, "Aguardando sorteio")

    def test_surpresinha_and_super_sete(self):
        response = self.client.post(reverse("loterias:detail", args=["supersete"]), {"acao": "surpresinha"}, follow=True)
        self.assertContains(response, "Bilhete de treino registrado")
        ticket = Ticket.objects.get()
        self.assertEqual(len(ticket.numbers), 7)
        self.assertEqual(ticket.contest, 910)

        data = {"acao": "registrar"} | {f"c{i}": str(d) for i, d in enumerate([8, 7, 6, 6, 0, 5, 4], start=1)}
        self.client.post(reverse("loterias:detail", args=["supersete"]), data)
        self.assertEqual(Ticket.objects.count(), 2)
        incomplete = {"acao": "registrar", "c1": "8"}
        response = self.client.post(reverse("loterias:detail", args=["supersete"]), incomplete)
        self.assertContains(response, "Marque um dígito em cada uma das 7 colunas")
        self.assertEqual(Ticket.objects.count(), 2)

    def test_pending_ticket_is_settled_when_visiting(self):
        Ticket.objects.create(
            user=self.user, lottery="megasena", contest=3069, numbers=[1, 2, 5, 19, 22, 44], stake=Decimal("6.00")
        )
        response = self.client.get(reverse("loterias:index"))
        self.assertContains(response, "Ganhou F$ 709,33")
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.status, Ticket.Status.WON)
        self.assertEqual(get_wallet(self.user).balance, Decimal("1000.00") + Decimal("709.33"))

    def test_insufficient_funds(self):
        wallet = get_wallet(self.user)
        wallet.balance = Decimal("1.00")
        wallet.save()
        url = reverse("loterias:detail", args=["megasena"])
        response = self.client.post(url, {"acao": "registrar", "n": ["1", "2", "3", "4", "5", "6"]})
        self.assertContains(response, "Saldo insuficiente")
        self.assertEqual(Ticket.objects.count(), 0)
