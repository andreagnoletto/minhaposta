from decimal import Decimal

from django.conf import settings
from django.db import models

from . import catalog


class ResultSnapshot(models.Model):
    """Resposta bruta da API da Caixa para um concurso, guardada para consulta off-line."""

    lottery = models.CharField("loteria", max_length=20)
    contest = models.PositiveIntegerField("concurso")
    payload = models.JSONField("resposta")
    fetched_at = models.DateTimeField("obtido em", auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["lottery", "contest"], name="unique_lottery_contest")]
        ordering = ["lottery", "-contest"]
        verbose_name = "resultado guardado"
        verbose_name_plural = "resultados guardados"

    def __str__(self):
        return f"{self.lottery} nº {self.contest}"


class Ticket(models.Model):
    """Bilhete de treino: aposta com fichas fictícias conferida contra o sorteio real."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Aguardando sorteio"
        WON = "WON", "Premiado"
        LOST = "LOST", "Não premiado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lottery_tickets")
    lottery = models.CharField("loteria", max_length=20)
    contest = models.PositiveIntegerField("concurso")
    numbers = models.JSONField("números", default=list)
    extra = models.JSONField("extra", default=list, blank=True)
    stake = models.DecimalField("valor", max_digits=10, decimal_places=2)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    hits = models.PositiveSmallIntegerField("acertos", default=0)
    second_hits = models.PositiveSmallIntegerField("acertos no 2º sorteio", default=0)
    extra_hits = models.PositiveSmallIntegerField("acertos no extra", default=0)
    tiers = models.JSONField("faixas premiadas", default=list, blank=True)
    payout = models.DecimalField("prêmio", max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField("conferido em", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "bilhete de treino"
        verbose_name_plural = "bilhetes de treino"

    def __str__(self):
        return f"{self.lottery_name} nº {self.contest} ({self.user})"

    @property
    def lottery_name(self) -> str:
        return catalog.get(self.lottery).name

    @property
    def numbers_label(self) -> str:
        return catalog.format_numbers(catalog.get(self.lottery), self.numbers)

    @property
    def extra_label(self) -> str:
        return catalog.format_extra(catalog.get(self.lottery), self.extra)

    @property
    def hits_label(self) -> str:
        if self.status == self.Status.PENDING:
            return ""
        lottery = catalog.get(self.lottery)
        parts = [f"{self.hits} acerto(s)"]
        if lottery.second_draw:
            parts.append(f"{self.second_hits} no 2º sorteio")
        if lottery.extra is not None and lottery.extra.playable:
            parts.append(f"{self.extra_hits} no extra")
        return ", ".join(parts)
