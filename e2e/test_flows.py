"""Fluxos principais no navegador: cadastro, bicho, roleta, volante e mobile."""

import random
from decimal import Decimal

from django.core.cache import cache

from casino import dice
from casino.services import play_dice
from loterias import results
from loterias.tests.test_results import sample
from wallet.services import get_wallet

from .base import MOBILE, PlaywrightTestCase

PAGES = ["/", "/bicho/", "/cassino/roleta/", "/cassino/caca-niquel/", "/cassino/dado/", "/loterias/megasena/", "/carteira/"]


class SignupAndBichoTests(PlaywrightTestCase):
    def test_signup_bet_and_draw_reveals_poste(self):
        self.goto("/cadastro/")
        self.page.get_by_label("Usuário:").fill("bia")
        self.page.get_by_label("Senha:", exact=True).fill("Fichas-Treino-2026")
        self.page.get_by_label("Confirmação de senha:").fill("Fichas-Treino-2026")
        self.page.get_by_role("button", name="Criar conta").click()
        self.page.wait_for_url(self.url("/"))
        self.assertIn("F$ 1000,00", self.page.locator(".saldo").inner_text())

        self.goto("/bicho/")
        self.page.get_by_role("button", name="09 Cobra 33–36").click()
        self.assertEqual(self.page.get_by_label("Palpite").input_value(), "09")
        self.page.get_by_role("button", name="Registrar aposta").click()
        self.page.wait_for_load_state("networkidle")
        self.assertIn("F$ 990,00", self.page.locator(".saldo").inner_text())
        self.assertIn("Aposta registrada", self.page.locator(".mensagens").inner_text())

        self.page.get_by_role("button", name="Sortear agora").click()
        self.page.wait_for_url("**/bicho/?sorteio=1#poste")
        self.page.wait_for_selector("#poste.revelado")
        self.assertTrue(self.is_in_viewport("#poste"), "o poste deve aparecer na tela após o sorteio")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "poste")
        self.assertEqual(self.page.locator("#poste .premio.revelado").count(), 5)
        self.assertIn("na cabeça", self.page.locator(".poste-cabeca").inner_text())


class RouletteTests(PlaywrightTestCase):
    reduced_motion = "no-preference"

    def test_live_region_announces_result_not_wheel_data(self):
        self.login(self.create_user())
        self.goto("/cassino/roleta/")
        self.assertEqual(self.page.get_by_role("button", name="17, preto").count(), 1)
        self.page.get_by_role("button", name="Girar a roleta").click()
        self.page.wait_for_url("**/cassino/roleta/?r=*")
        self.page.wait_for_selector(".resultado.revelado", timeout=8000)

        live = self.accessible_text("section[aria-live]")
        self.assertFalse(live.startswith("["), f"região ao vivo começa com JSON: {live[:60]!r}")
        self.assertTrue(live.startswith("Saiu"), f"leitor de tela ouviria: {live[:80]!r}")
        self.assertRegex(live, r"(Ganhou|Perdeu) F\$")
        self.assertTrue(self.is_in_viewport(".resultado-numero"))


class LotteryTicketTests(PlaywrightTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        results.store(sample("megasena"))
        self.login(self.create_user())

    def test_volante_blocks_extra_picks(self):
        self.goto("/loterias/megasena/")
        for value in ["1", "2", "3", "4", "5", "6"]:
            self.page.locator(f'input[name="n"][value="{value}"]').check(force=True)
        contador = self.page.locator("[data-contador]")
        self.assertEqual(contador.inner_text(), "(6 de 6)")
        self.assertTrue(contador.evaluate("el => el.classList.contains('completo')"))
        self.assertEqual(self.page.locator('input[name="n"]:disabled').count(), 54)
        self.assertEqual(self.page.locator(".casa-bloqueada").count(), 54)

        self.page.locator('input[name="n"][value="6"]').uncheck(force=True)
        self.assertEqual(self.page.locator('input[name="n"]:disabled').count(), 0)
        self.assertEqual(contador.inner_text(), "(5 de 6)")

    def test_server_error_is_focused_and_visible(self):
        self.goto("/loterias/megasena/")
        for value in ["1", "2", "3", "4", "5", "6"]:
            self.page.locator(f'input[name="n"][value="{value}"]').check(force=True)
        # Simula um cliente sem o bloqueio do JavaScript marcando um 7º número.
        self.page.evaluate(
            """() => { const c = document.querySelector('input[name="n"][value="7"]'); c.disabled = false; c.checked = true; }"""
        )
        self.page.get_by_role("button", name="Registrar para o próximo concurso (F$ 6,00)").click()
        self.page.wait_for_load_state("networkidle")

        erro = self.page.locator("#bilhete .erro-lista")
        self.assertIn("Marque exatamente 6 números", erro.inner_text())
        self.assertEqual(erro.get_attribute("role"), "alert")
        self.assertTrue(self.is_in_viewport("#bilhete .erro-lista"), "o erro deve estar visível sem rolar")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "bilhete")
        self.assertEqual(self.page.locator('input[name="n"]:checked').count(), 7, "a marcação é preservada")


class MobileLayoutTests(PlaywrightTestCase):
    viewport = MOBILE

    def setUp(self):
        super().setUp()
        cache.clear()
        results.store(sample("megasena"))
        user = self.create_user()
        get_wallet(user)
        play_dice(user, pick=1, stake=Decimal("10"), rng=random.Random(1))
        self.login(user)

    def test_pages_have_no_horizontal_overflow(self):
        for path in PAGES:
            with self.subTest(path=path):
                self.goto(path)
                self.assertFalse(self.has_horizontal_overflow(), f"{path} rola na horizontal em {MOBILE['width']}px")

    def test_tables_are_wrapped_for_scrolling(self):
        for path in ["/carteira/", "/cassino/caca-niquel/"]:
            with self.subTest(path=path):
                self.goto(path)
                naked = self.page.evaluate(
                    "() => [...document.querySelectorAll('table.dados')].filter(t => !t.closest('.tabela-rolagem')).length"
                )
                self.assertEqual(naked, 0, f"{path} tem tabela sem .tabela-rolagem")


class LandmarkTests(PlaywrightTestCase):
    def test_every_page_has_basic_structure(self):
        self.login(self.create_user())
        for path in PAGES:
            with self.subTest(path=path):
                self.goto(path)
                self.assertEqual(self.page.locator("h1").count(), 1)
                self.assertEqual(self.page.locator("main#conteudo").count(), 1)
                self.assertEqual(self.page.locator('a[href="#conteudo"]').count(), 1)
                self.assertTrue(self.page.locator("html").get_attribute("lang").startswith("pt"))
