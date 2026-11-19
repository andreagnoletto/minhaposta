"""Bilhete de treino: aposta com fichas fictícias conferida contra o sorteio real.

O bilhete custa, em F$, o mesmo que a aposta mínima custa em R$. Quando o
concurso sai, os acertos são contados contra as dezenas oficiais e o prêmio
creditado é o valor real pago pela Caixa naquela faixa (também em F$).
"""

import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from wallet.models import Transaction
from wallet.services import credit, debit, get_wallet

from . import catalog, results
from .models import Ticket


class InvalidPick(ValueError):
    """Marcação fora das regras do volante."""


def surpresinha(lottery, rng=random):
    """Números e extra aleatórios, como a surpresinha da lotérica."""
    if lottery.kind == "colunas":
        numbers = [rng.randrange(10) for _ in range(lottery.columns)]
    else:
        numbers = sorted(rng.sample(list(lottery.numbers), lottery.picks))
    extra = []
    if lottery.extra is not None and lottery.extra.playable:
        extra = sorted(rng.sample(range(1, lottery.extra.pool + 1), lottery.extra.picks))
    return numbers, extra


def validate_pick(lottery, numbers, extra=()):
    """Normaliza a marcação (listas de inteiros) e valida contra o volante."""
    if not lottery.playable:
        raise InvalidPick(f"{lottery.name} não tem números para marcar.")
    try:
        numbers = [int(n) for n in numbers]
    except (TypeError, ValueError) as exc:
        raise InvalidPick("Marcação inválida.") from exc

    if lottery.kind == "colunas":
        if len(numbers) != lottery.columns:
            raise InvalidPick(f"Marque um dígito em cada uma das {lottery.columns} colunas.")
        if any(n < 0 or n > 9 for n in numbers):
            raise InvalidPick("Cada coluna aceita um dígito de 0 a 9.")
    else:
        if len(set(numbers)) != len(numbers):
            raise InvalidPick("Há números repetidos.")
        if len(numbers) != lottery.picks:
            raise InvalidPick(f"Marque exatamente {lottery.picks} números (você marcou {len(numbers)}).")
        if any(n not in lottery.numbers for n in numbers):
            raise InvalidPick(f"Os números vão de {lottery.first:0{lottery.digits}d} a {lottery.last}.")
        numbers = sorted(numbers)

    extra_list: list[int] = []
    if lottery.extra is not None and lottery.extra.playable:
        try:
            extra_list = sorted({int(e) for e in extra})
        except (TypeError, ValueError) as exc:
            raise InvalidPick(f"{lottery.extra.label}: escolha inválida.") from exc
        if len(extra_list) != lottery.extra.picks or any(e < 1 or e > lottery.extra.pool for e in extra_list):
            raise InvalidPick(f"{lottery.extra.label}: escolha {lottery.extra.picks} opção(ões) entre 1 e {lottery.extra.pool}.")
    return numbers, extra_list


def _ints(values):
    return [int(v) for v in values]


def score(lottery, numbers, extra, result):
    """Conta acertos de um jogo contra um ``DrawResult`` e lista as faixas atingidas."""
    if lottery.kind == "colunas":
        hits = sum(1 for mine, drawn in zip(numbers, _ints(result.numbers)) if mine == drawn)
    else:
        hits = len(set(numbers) & set(_ints(result.numbers)))

    second_hits = 0
    if lottery.second_draw and result.second_numbers:
        second_hits = len(set(numbers) & set(_ints(result.second_numbers)))

    extra_hits = 0
    if lottery.extra is not None and lottery.extra.playable and extra:
        if lottery.extra.options:
            drawn_names = {value.casefold() for value in result.extra_values}
            drawn_extra = {i + 1 for i, name in enumerate(lottery.extra.options) if name.casefold() in drawn_names}
        else:
            drawn_extra = set(_ints(result.extra_values))
        extra_hits = len(set(extra) & drawn_extra)

    won = []
    for tier in lottery.tiers:
        relevant_hits = hits
        if lottery.second_draw and tier.label.startswith("2º"):
            relevant_hits = second_hits
        if tier.hits is not None and tier.hits != relevant_hits:
            continue
        if tier.extra is not None and extra_hits not in tier.extra:
            continue
        won.append(tier.label)

    payout = Decimal("0.00")
    jackpot_alone = False
    for label in won:
        paid = result.tier(label)
        if paid is None:
            continue
        if paid.prize > 0:
            payout += paid.prize
        elif label == lottery.tiers[0].label and paid.winners == 0:
            # Ninguém acertou de verdade: o bilhete de treino levaria o acumulado sozinho.
            payout += result.jackpot
            jackpot_alone = True
    return {
        "hits": hits,
        "second_hits": second_hits,
        "extra_hits": extra_hits,
        "tiers": won,
        "payout": payout.quantize(Decimal("0.01")),
        "jackpot_alone": jackpot_alone,
    }


def next_contest(lottery) -> int:
    """Número do próximo concurso segundo o último snapshot local."""
    known = results.known_latest(lottery.slug)
    if known is None:
        raise results.ResultsUnavailable("Não foi possível descobrir o próximo concurso. Tente de novo mais tarde.")
    return known.next_contest or known.contest + 1


def place_ticket(user, lottery, numbers, extra=(), contest=None) -> Ticket:
    """Debita o preço da aposta mínima e registra o bilhete para ``contest``.

    Levanta ``InvalidPick``, ``wallet.services.InsufficientFunds`` ou
    ``results.ResultsUnavailable`` sem criar nada.
    """
    numbers, extra = validate_pick(lottery, numbers, extra)
    if contest is None:
        contest = next_contest(lottery)  # fora da transação: pode ir à rede
    return _create_ticket(user, lottery, numbers, extra, contest)


@transaction.atomic
def _create_ticket(user, lottery, numbers, extra, contest) -> Ticket:
    wallet = get_wallet(user)
    label = catalog.format_numbers(lottery, numbers)
    if extra:
        label += f" + {catalog.format_extra(lottery, extra)}"
    debit(
        wallet,
        lottery.price,
        Transaction.Game.LOTERIA,
        f"Bilhete de treino: {lottery.name} nº {contest} ({label})",
    )
    return Ticket.objects.create(
        user=user, lottery=lottery.slug, contest=contest, numbers=numbers, extra=extra, stake=lottery.price
    )


@transaction.atomic
def settle(ticket: Ticket, result) -> Ticket | None:
    """Confere o bilhete contra ``result``, grava acertos e credita o prêmio."""
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status != Ticket.Status.PENDING:
        return None
    lottery = catalog.get(ticket.lottery)
    outcome = score(lottery, ticket.numbers, ticket.extra, result)
    ticket.hits = outcome["hits"]
    ticket.second_hits = outcome["second_hits"]
    ticket.extra_hits = outcome["extra_hits"]
    ticket.tiers = outcome["tiers"]
    ticket.payout = outcome["payout"]
    ticket.status = Ticket.Status.WON if outcome["tiers"] else Ticket.Status.LOST
    ticket.checked_at = timezone.now()
    ticket.save(update_fields=["hits", "second_hits", "extra_hits", "tiers", "payout", "status", "checked_at"])
    if ticket.payout > 0:
        credit(
            get_wallet(ticket.user),
            ticket.payout,
            Transaction.Kind.PAYOUT,
            Transaction.Game.LOTERIA,
            f"Prêmio: {lottery.name} nº {ticket.contest}, {', '.join(outcome['tiers'])}",
        )
    return ticket


def check_ticket(ticket: Ticket) -> bool:
    """Confere o bilhete se o concurso já saiu. Devolve ``True`` quando liquidou."""
    if ticket.status != Ticket.Status.PENDING:
        return False
    result = results.for_contest(ticket.lottery, ticket.contest)
    if result is None:
        return False
    return settle(ticket, result) is not None


def settle_pending(user) -> list[Ticket]:
    """Confere todos os bilhetes pendentes do usuário cujo concurso já saiu."""
    settled = []
    for ticket in Ticket.objects.filter(user=user, status=Ticket.Status.PENDING).order_by("contest", "id"):
        if check_ticket(ticket):
            ticket.refresh_from_db()
            settled.append(ticket)
    return settled
