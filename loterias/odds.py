"""Probabilidades das loterias, calculadas por combinatória.

Loterias de números seguem a distribuição hipergeométrica: de ``pool``
números, ``drawn`` são sorteados e o apostador marcou ``picks``. A chance
de acertar exatamente ``hits`` é C(drawn, hits) · C(pool − drawn, picks − hits)
÷ C(pool, picks). O Super Sete (um dígito por coluna) é binomial.
"""

from fractions import Fraction
from math import comb


def hypergeometric(pool: int, drawn: int, picks: int, hits: int) -> Fraction:
    """Chance de exatamente ``hits`` acertos ao marcar ``picks`` de ``pool`` números."""
    if hits < 0 or hits > min(drawn, picks) or picks - hits > pool - drawn:
        return Fraction(0)
    return Fraction(comb(drawn, hits) * comb(pool - drawn, picks - hits), comb(pool, picks))


def binomial(columns: int, hits: int, base: int = 10) -> Fraction:
    """Chance de acertar exatamente ``hits`` colunas, cada uma com ``base`` dígitos."""
    if hits < 0 or hits > columns:
        return Fraction(0)
    p = Fraction(1, base)
    return comb(columns, hits) * p**hits * (1 - p) ** (columns - hits)


def main_probability(lottery, hits: int) -> Fraction:
    """Chance de ``hits`` acertos nos números principais da aposta mínima."""
    if lottery.kind == "colunas":
        return binomial(lottery.columns, hits)
    return hypergeometric(lottery.pool, lottery.drawn, lottery.picks, hits)


def extra_probability(lottery, hits: int) -> Fraction:
    """Chance de ``hits`` acertos no extra (mês, trevos, time)."""
    extra = lottery.extra
    if extra is None:
        return Fraction(1) if hits == 0 else Fraction(0)
    return hypergeometric(extra.pool, extra.drawn, extra.picks, hits)


def tier_probability(lottery, tier) -> Fraction:
    """Chance de uma faixa de premiação para a aposta mínima."""
    if tier.extra is None:
        p_extra = Fraction(1)
    else:
        p_extra = sum((extra_probability(lottery, k) for k in tier.extra), Fraction(0))
    if tier.hits is None:
        return p_extra
    return main_probability(lottery, tier.hits) * p_extra


def one_in(probability: Fraction) -> float:
    """"Uma chance em N" a partir da probabilidade."""
    return float(1 / probability) if probability else float("inf")


def one_in_label(value: float) -> str:
    """"1 em N" formatado em pt-BR: 50.063.860, ou 43,5 quando é pequeno e quebrado."""
    if value == float("inf"):
        return "∞"
    if value < 100 and abs(value - round(value)) >= 0.05:
        return f"{value:.1f}".replace(".", ",")
    return f"{round(value):,}".replace(",", ".")


def odds_table(lottery) -> list[dict]:
    """Linhas da tabela de chances: faixa, probabilidade, 1 em N e regra de prêmio."""
    rows = []
    for tier in lottery.tiers:
        probability = tier_probability(lottery, tier)
        rows.append(
            {
                "label": tier.label,
                "probability": probability,
                "one_in": one_in(probability),
                "one_in_label": one_in_label(one_in(probability)),
                "share": tier.share,
            }
        )
    return rows


def any_prize_probability(lottery) -> Fraction:
    """Chance de ganhar alguma coisa (qualquer faixa) na aposta mínima.

    Faixas com condição sobre o extra e faixas só do extra são contadas
    como eventos independentes dos acertos principais; o resultado é
    1 − P(não ganhar nada).
    """
    exclusive = [t for t in lottery.tiers if t.hits is not None]
    independent = [t for t in lottery.tiers if t.hits is None]
    p_main = sum((tier_probability(lottery, t) for t in exclusive), Fraction(0))
    lose = 1 - p_main
    for tier in independent:
        lose *= 1 - tier_probability(lottery, tier)
    return 1 - lose


def total_combinations(lottery) -> int:
    """Quantas apostas mínimas diferentes existem (para "garantir" o prêmio máximo)."""
    if lottery.kind == "colunas":
        return 10**lottery.columns
    total = comb(lottery.pool, lottery.picks)
    if lottery.extra is not None and lottery.extra.playable:
        total *= comb(lottery.extra.pool, lottery.extra.picks)
    return total
