"""Baixa o último resultado de cada loteria da Caixa e guarda no banco."""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from loterias import catalog, results
from loterias.models import Ticket


class Command(BaseCommand):
    help = "Atualiza os últimos resultados das loterias da Caixa (API pública do portal)."

    def add_arguments(self, parser):
        parser.add_argument("loterias", nargs="*", help="slugs (megasena, quina…); vazio = todas")

    def handle(self, *args, **options):
        slugs = options["loterias"] or list(catalog.LOTTERIES)
        updated = {}
        for slug in slugs:
            if slug not in catalog.LOTTERIES:
                self.stderr.write(f"{slug}: loteria desconhecida")
                continue
            try:
                result = results.fetch(slug)
            except results.ResultsUnavailable as exc:
                self.stderr.write(f"{slug}: {exc}")
                continue
            cache.set(f"loterias:ultimo:{slug}", result, results.CACHE_TTL)
            cache.delete(f"loterias:falha:{slug}")
            updated[slug] = result.contest
            when = result.date.strftime("%d/%m/%Y") if result.date else "?"
            self.stdout.write(f"{result.name}: concurso {result.contest} de {when}, {' '.join(result.numbers)}")

        pending = (
            Ticket.objects.filter(status=Ticket.Status.PENDING, lottery__in=updated)
            .values_list("lottery", "contest")
            .distinct()
        )
        for slug, contest in pending:
            latest = results.known_latest(slug)
            if contest > updated[slug] or latest is None or latest.contest == contest:
                continue
            try:
                results.fetch(slug, contest)
            except results.ResultsUnavailable as exc:
                self.stderr.write(f"{slug} concurso {contest}: {exc}")
