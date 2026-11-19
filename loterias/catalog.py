"""Catálogo das loterias da Caixa: regras, preços, dias de sorteio e faixas.

Os dados vêm das páginas oficiais (loterias.caixa.gov.br), conferidos em
``CHECKED_ON``. Preços e calendário mudam; o último resultado e a data do
próximo concurso vêm sempre da API em ``loterias.results``.
"""

from dataclasses import dataclass
from decimal import Decimal

CHECKED_ON = "11/10/2026"
OFFICIAL_SITE = "https://loterias.caixa.gov.br/"
ONLINE_SITE = "https://www.loteriasonline.caixa.gov.br/"
MONTHS = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


@dataclass(frozen=True)
class Tier:
    """Faixa de premiação. ``label`` é o mesmo texto que a API da Caixa usa."""

    label: str
    hits: int | None  # acertos nos números principais; None = faixa só do extra
    extra: tuple[int, ...] | None = None  # acertos exigidos no extra; None = indiferente
    share: str = ""  # como o prêmio é formado


@dataclass(frozen=True)
class Extra:
    """Elemento extra do volante: mês da sorte, trevos, time do coração."""

    label: str
    pool: int
    picks: int
    drawn: int
    options: tuple[str, ...] = ()
    playable: bool = True  # entra no bilhete de treino?


@dataclass(frozen=True)
class Lottery:
    slug: str
    name: str
    kind: str  # numeros | colunas | bilhete | esportiva
    tagline: str
    price: Decimal
    draw_days: str
    prize_share: Decimal  # % da arrecadação que vira prêmio bruto
    tiers: tuple[Tier, ...] = ()
    pool: int = 0
    picks: int = 0
    drawn: int = 0
    first: int = 1
    columns: int = 0
    extra: Extra | None = None
    second_draw: bool = False
    how_to: tuple[str, ...] = ()
    note: str = ""
    page: str = ""

    @property
    def api_slug(self) -> str:
        return self.slug

    @property
    def official_url(self) -> str:
        return f"{OFFICIAL_SITE}Paginas/{self.page}.aspx"

    @property
    def playable(self) -> bool:
        return self.kind in ("numeros", "colunas")

    @property
    def last(self) -> int:
        return self.first + self.pool - 1

    @property
    def numbers(self) -> range:
        return range(self.first, self.last + 1)

    @property
    def digits(self) -> int:
        """Quantos dígitos tem um número impresso no volante (00–99 ou 01–60)."""
        return len(str(self.last))

    @property
    def house_share(self) -> Decimal:
        return Decimal("100") - self.prize_share


def _pct(label, hits, pct, extra=None):
    return Tier(label, hits, extra, f"{pct}% do prêmio")


def _fixed(label, hits, value, extra=None):
    return Tier(label, hits, extra, f"R$ {value} fixos")


LOTTERIES: dict[str, Lottery] = {}


def _add(lottery: Lottery) -> Lottery:
    LOTTERIES[lottery.slug] = lottery
    return lottery


_add(Lottery(
    slug="megasena", name="Mega-Sena", kind="numeros", page="Mega-Sena",
    tagline="Seis dezenas entre sessenta. A loteria mais famosa e a mais difícil de acertar.",
    price=Decimal("6.00"), draw_days="terças e quintas às 21h, domingos às 11h",
    prize_share=Decimal("43.79"), pool=60, picks=6, drawn=6,
    tiers=(_pct("6 acertos", 6, 40), _pct("5 acertos", 5, 13), _pct("4 acertos", 4, 15)),
    how_to=(
        "Marque de 6 a 20 números entre 1 e 60. A aposta mínima tem 6 números.",
        "Ganha quem acerta 4, 5 ou 6 dezenas. O prêmio de cada faixa é dividido entre os acertadores.",
        "Dos 43,79% que viram prêmio, 22% ficam guardados para os concursos de final 0 ou 5 e 10% para a Mega da Virada.",
    ),
))

_add(Lottery(
    slug="quina", name="Quina", kind="numeros", page="Quina",
    tagline="Cinco dezenas entre oitenta, com sorteio quase todo dia.",
    price=Decimal("3.00"), draw_days="segunda a sexta às 21h, domingos às 11h",
    prize_share=Decimal("43.79"), pool=80, picks=5, drawn=5,
    tiers=(_pct("5 acertos", 5, 35), _pct("4 acertos", 4, 15), _pct("3 acertos", 3, 10), _pct("2 acertos", 2, 10)),
    how_to=(
        "Marque de 5 a 15 números entre 1 e 80. A aposta mínima tem 5 números.",
        "Ganha quem acerta 2, 3, 4 ou 5 dezenas.",
        "Os 30% restantes do prêmio ficam acumulados para a Quina de São João e para os concursos de final 5.",
    ),
))

_add(Lottery(
    slug="lotofacil", name="Lotofácil", kind="numeros", page="Lotofacil",
    tagline="Quinze dezenas entre vinte e cinco. É fácil acertar pouco e dificílimo acertar tudo.",
    price=Decimal("3.50"), draw_days="segunda a sexta às 21h, domingos às 11h",
    prize_share=Decimal("43.79"), pool=25, picks=15, drawn=15,
    tiers=(
        _pct("15 acertos", 15, 62), _pct("14 acertos", 14, 13),
        _fixed("13 acertos", 13, "35,00"), _fixed("12 acertos", 12, "14,00"), _fixed("11 acertos", 11, "7,00"),
    ),
    how_to=(
        "Marque de 15 a 20 números entre 1 e 25. A aposta mínima tem 15 números.",
        "Ganha quem acerta 11, 12, 13, 14 ou 15 dezenas. As três faixas menores têm valor fixo.",
        "Nos concursos de final 0 a faixa de 15 acertos recebe 72% em vez de 62%.",
    ),
))

_add(Lottery(
    slug="lotomania", name="Lotomania", kind="numeros", page="Lotomania",
    tagline="Cinquenta dezenas entre cem. Acertar nenhuma também paga.",
    price=Decimal("3.00"), draw_days="segundas, quartas e sextas às 21h",
    prize_share=Decimal("43.79"), pool=100, picks=50, drawn=20, first=0,
    tiers=(
        _pct("20 acertos", 20, 45), _pct("19 acertos", 19, 16), _pct("18 acertos", 18, 10),
        _pct("17 acertos", 17, 7), _pct("16 acertos", 16, 7), _pct("15 acertos", 15, 7), _pct("0 acertos", 0, 8),
    ),
    how_to=(
        "Marque 50 números entre 00 e 99. São sorteadas 20 dezenas.",
        "Ganha quem acerta 15, 16, 17, 18, 19 ou 20 dezenas, ou nenhuma.",
        "Zero acertos é tão improvável quanto vinte: 1 em 11.372.635.",
    ),
))

_add(Lottery(
    slug="duplasena", name="Dupla Sena", kind="numeros", page="Dupla-Sena",
    tagline="Seis dezenas entre cinquenta, dois sorteios por concurso.",
    price=Decimal("3.00"), draw_days="segundas, quartas e sextas às 21h",
    prize_share=Decimal("43.79"), pool=50, picks=6, drawn=6, second_draw=True,
    tiers=(
        _pct("1º sorteio: 6 acertos", 6, 30), _pct("1º sorteio: 5 acertos", 5, 10),
        _pct("1º sorteio: 4 acertos", 4, 8), _pct("1º sorteio: 3 acertos", 3, 4),
        _pct("2º sorteio: 6 acertos", 6, 11), _pct("2º sorteio: 5 acertos", 5, 9),
        _pct("2º sorteio: 4 acertos", 4, 8), _pct("2º sorteio: 3 acertos", 3, 4),
    ),
    how_to=(
        "Marque de 6 a 15 números entre 1 e 50. A aposta mínima tem 6 números.",
        "O mesmo bilhete concorre em dois sorteios. Ganha quem acerta 3, 4, 5 ou 6 em qualquer um deles.",
        "16% do prêmio ficam acumulados para o concurso especial de Páscoa.",
    ),
))

_add(Lottery(
    slug="timemania", name="Timemania", kind="numeros", page="Timemania",
    tagline="Dez dezenas entre oitenta, sete sorteadas, mais um time do coração.",
    price=Decimal("3.50"), draw_days="terças e quintas às 21h, domingos às 11h",
    prize_share=Decimal("50.00"), pool=80, picks=10, drawn=7,
    extra=Extra("Time do Coração", pool=80, picks=1, drawn=1, playable=False),
    tiers=(
        _pct("7 acertos", 7, 50), _pct("6 acertos", 6, 20), _pct("5 acertos", 5, 20),
        _fixed("4 acertos", 4, "10,50"), _fixed("3 acertos", 3, "3,50"),
        _fixed("Time do Coração", None, "8,50", extra=(1,)),
    ),
    how_to=(
        "Marque 10 números entre 1 e 80 e escolha um clube de futebol como time do coração.",
        "São sorteadas 7 dezenas e um time. Ganha quem acerta 3, 4, 5, 6 ou 7 dezenas ou o time.",
        "Os valores fixos saem primeiro; o que sobra é dividido entre 7, 6 e 5 acertos, com 10% guardados para os concursos de final 0 ou 5.",
    ),
    note="No bilhete de treino o time do coração fica de fora: a conferência usa só as dezenas.",
))

_add(Lottery(
    slug="diadesorte", name="Dia de Sorte", kind="numeros", page="Dia-de-Sorte",
    tagline="Sete dezenas entre trinta e uma, mais um mês da sorte.",
    price=Decimal("2.50"), draw_days="segunda a sexta às 21h, domingos às 11h",
    prize_share=Decimal("43.79"), pool=31, picks=7, drawn=7,
    extra=Extra("Mês da Sorte", pool=12, picks=1, drawn=1, options=MONTHS),
    tiers=(
        _pct("7 acertos", 7, 70), _pct("6 acertos", 6, 30),
        _fixed("5 acertos", 5, "25,00"), _fixed("4 acertos", 4, "5,00"),
        _fixed("Mês da Sorte", None, "2,50", extra=(1,)),
    ),
    how_to=(
        "Marque de 7 a 15 números entre 1 e 31 e um mês da sorte. A aposta mínima tem 7 números.",
        "Ganha quem acerta 4, 5, 6 ou 7 dezenas. Acertar o mês paga à parte, somado ao resto.",
    ),
))

_add(Lottery(
    slug="supersete", name="Super Sete", kind="colunas", page="Super-Sete",
    tagline="Sete colunas, um dígito de 0 a 9 em cada. Um em dez milhões.",
    price=Decimal("3.00"), draw_days="segundas, quartas e sextas às 21h",
    prize_share=Decimal("43.79"), columns=7,
    tiers=(
        _pct("7 acertos", 7, 55), _pct("6 acertos", 6, 15), _pct("5 acertos", 5, 15),
        _pct("4 acertos", 4, 15), _fixed("3 acertos", 3, "6,00"),
    ),
    how_to=(
        "O volante tem 7 colunas com os dígitos de 0 a 9. Marque um dígito em cada coluna.",
        "É sorteado um dígito por coluna. Ganha quem acerta 3, 4, 5, 6 ou 7 colunas.",
    ),
))

_add(Lottery(
    slug="maismilionaria", name="+Milionária", kind="numeros", page="Mais-Milionaria",
    tagline="Seis dezenas entre cinquenta e dois trevos entre seis. Prêmio mínimo de R$ 10 milhões.",
    price=Decimal("6.00"), draw_days="quartas às 21h, domingos às 11h",
    prize_share=Decimal("43.79"), pool=50, picks=6, drawn=6,
    extra=Extra("Trevos", pool=6, picks=2, drawn=2),
    tiers=(
        _pct("6 acertos + 2 trevos", 6, 62, extra=(2,)),
        _pct("6 acertos + 1 ou nenhum trevo", 6, 10, extra=(0, 1)),
        _pct("5 acertos + 2 trevos", 5, 8, extra=(2,)),
        _pct("5 acertos + 1 ou nenhum trevo", 5, 8, extra=(0, 1)),
        _pct("4 acertos + 2 trevos", 4, 6, extra=(2,)),
        _pct("4 acertos + 1 ou nenhum trevo", 4, 6, extra=(0, 1)),
        _fixed("3 acertos + 2 trevos", 3, "50,00", extra=(2,)),
        _fixed("3 acertos + 1 trevo", 3, "24,00", extra=(1,)),
        _fixed("2 acertos + 2 trevos", 2, "12,00", extra=(2,)),
        _fixed("2 acertos + 1 trevo", 2, "6,00", extra=(1,)),
    ),
    how_to=(
        "Marque 6 números entre 1 e 50 e 2 trevos entre 1 e 6.",
        "São dez faixas de prêmio, combinando acertos de números e de trevos.",
        "A faixa principal tem prêmio mínimo garantido de R$ 10 milhões.",
    ),
))

_add(Lottery(
    slug="federal", name="Loteria Federal", kind="bilhete", page="Federal",
    tagline="Bilhetes numerados, como os da banca do bicho, mas legais e com prêmio fixo.",
    price=Decimal("4.00"), draw_days="quartas-feiras (Quartou) e domingos; Enricou uma vez por mês",
    prize_share=Decimal("60.00"),
    how_to=(
        "Você compra um bilhete (ou uma fração dele) já numerado. Não há números para escolher.",
        "São sorteados cinco bilhetes premiados, mais prêmios por milhar, centena, dezena e aproximações do 1º prêmio.",
        "A fração custa R$ 4,00 no Quartou e R$ 10,00 no Enricou; o bilhete inteiro tem 10 frações.",
        "É da Loteria Federal que o jogo do bicho tira os resultados usados nas apostas.",
    ),
))

_add(Lottery(
    slug="loteca", name="Loteca", kind="esportiva", page="Loteca",
    tagline="Quatorze jogos de futebol: coluna 1, empate ou coluna 2.",
    price=Decimal("4.00"), draw_days="concursos semanais; apostas até sábado às 14h",
    prize_share=Decimal("55.00"),
    how_to=(
        "Para cada um dos 14 jogos, marque vitória do time 1, empate ou vitória do time 2.",
        "A aposta mínima (R$ 4,00) inclui um palpite duplo; mais duplos e triplos custam mais e aumentam a chance.",
        "Ganha quem acerta 13 ou 14 resultados. A Caixa estima 1 chance em 2.391.485 de acertar os 14 com a aposta mínima.",
    ),
))


def get(slug: str) -> Lottery:
    """Loteria pelo slug; ``KeyError`` se não existir."""
    return LOTTERIES[slug]


def playable() -> list[Lottery]:
    return [lottery for lottery in LOTTERIES.values() if lottery.playable]


def format_numbers(lottery: Lottery, numbers) -> str:
    """Números como aparecem no bilhete: "05 19 22" ou, no Super Sete, "8 7 6 6 0 5 4"."""
    if lottery.kind == "colunas":
        return " ".join(str(n) for n in numbers)
    return " ".join(f"{int(n):0{lottery.digits}d}" for n in numbers)


def format_extra(lottery: Lottery, extra) -> str:
    """Extra legível: "Janeiro", "3 e 6"."""
    if lottery.extra is None or not extra:
        return ""
    if lottery.extra.options:
        return ", ".join(lottery.extra.options[int(i) - 1] for i in extra)
    return " e ".join(str(i) for i in extra)
