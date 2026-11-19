from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.formats import number_format

from wallet.services import InsufficientFunds

from . import catalog, odds, results, services
from .forms import TicketForm
from .models import Ticket


def _announce_settled(request, settled):
    for ticket in settled:
        if ticket.payout > 0:
            messages.success(
                request,
                f"{ticket.lottery_name} nº {ticket.contest} conferida: {ticket.hits_label}. "
                f"Ganhou F$ {number_format(ticket.payout, 2)} ({', '.join(ticket.tiers)}).",
            )
        else:
            messages.warning(
                request, f"{ticket.lottery_name} nº {ticket.contest} conferida: {ticket.hits_label}. Sem prêmio."
            )


def index(request):
    lotteries = list(catalog.LOTTERIES.values())
    found = results.known_latest_all(lottery.slug for lottery in lotteries)
    cards = []
    for lottery in lotteries:
        top = odds.odds_table(lottery)[0] if lottery.tiers else None
        cards.append({"lottery": lottery, "result": found.get(lottery.slug), "top": top})
    tickets = []
    if request.user.is_authenticated:
        _announce_settled(request, services.settle_pending(request.user))
        tickets = Ticket.objects.filter(user=request.user)[:20]
    context = {
        "cards": cards,
        "nav_lotteries": lotteries,
        "tickets": tickets,
        "checked_on": catalog.CHECKED_ON,
        "official_site": catalog.OFFICIAL_SITE,
        "online_site": catalog.ONLINE_SITE,
    }
    return render(request, "loterias/index.html", context)


def legal(request):
    context = {
        "official_site": catalog.OFFICIAL_SITE,
        "online_site": catalog.ONLINE_SITE,
        "checked_on": catalog.CHECKED_ON,
        "lotteries": list(catalog.LOTTERIES.values()),
        "nav_lotteries": list(catalog.LOTTERIES.values()),
    }
    return render(request, "loterias/legal.html", context)


def detail(request, slug):
    try:
        lottery = catalog.get(slug)
    except KeyError:
        raise Http404("Loteria desconhecida.")

    result = results.known_latest(slug)
    form = TicketForm(lottery, request.POST or None) if lottery.playable else None
    quick = None

    if request.method == "POST" and lottery.playable:
        action = request.POST.get("acao", "registrar")
        if action == "conferir":
            if form.is_valid():
                if result is None:
                    form.add_error(None, "Sem resultado disponível para conferir agora.")
                else:
                    quick = services.score(lottery, form.cleaned_data["numbers"], form.cleaned_data["extra_list"], result)
        else:
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if action == "surpresinha":
                numbers, extra = services.surpresinha(lottery)
                form = TicketForm(lottery)
                valid = True
            else:
                valid = form.is_valid()
                numbers = form.cleaned_data.get("numbers") if valid else None
                extra = form.cleaned_data.get("extra_list") if valid else None
            if valid:
                try:
                    ticket = services.place_ticket(request.user, lottery, numbers, extra)
                except (InsufficientFunds, results.ResultsUnavailable, services.InvalidPick) as exc:
                    form.add_error(None, str(exc))
                else:
                    messages.success(
                        request,
                        f"Bilhete de treino registrado: {lottery.name} nº {ticket.contest}, "
                        f"{ticket.numbers_label}{' + ' + ticket.extra_label if ticket.extra_label else ''}, "
                        f"F$ {number_format(ticket.stake, 2)}. Volte depois do sorteio para conferir.",
                    )
                    return redirect("loterias:detail", slug=slug)

    my_tickets = []
    if request.user.is_authenticated:
        _announce_settled(request, services.settle_pending(request.user))
        my_tickets = Ticket.objects.filter(user=request.user, lottery=slug)[:15]

    table = odds.odds_table(lottery) if lottery.tiers else []
    combinations = odds.total_combinations(lottery) if lottery.playable else None
    context = {
        "lottery": lottery,
        "result": result,
        "table": table,
        "any_prize_label": odds.one_in_label(odds.one_in(odds.any_prize_probability(lottery))) if lottery.tiers else None,
        "combinations": combinations,
        "cost_all": lottery.price * combinations if combinations else None,
        "form": form,
        "quick": quick,
        "my_tickets": my_tickets,
        "checked_on": catalog.CHECKED_ON,
        "online_site": catalog.ONLINE_SITE,
        "nav_lotteries": list(catalog.LOTTERIES.values()),
    }
    return render(request, "loterias/detail.html", context)
