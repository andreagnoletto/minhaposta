"""Resultados oficiais: consulta à API pública do portal de loterias da Caixa.

Endpoint: ``https://servicebus2.caixa.gov.br/portaldeloterias/api/<loteria>``
(último concurso) ou ``.../api/<loteria>/<numero>``. Não é documentado
oficialmente, mas é o que o próprio site da Caixa consome.

Cada resposta é guardada em ``ResultSnapshot``; se a API falhar, a página
mostra o último resultado conhecido com a marca ``stale``.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from . import catalog
from .models import ResultSnapshot

API_URL = "https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}"
TIMEOUT = 8  # segundos
CACHE_TTL = 10 * 60
FAILURE_TTL = 90
USER_AGENT = "Mozilla/5.0 (MinhaPosta; simulador educativo)"

log = logging.getLogger(__name__)


class ResultsUnavailable(Exception):
    """A API não respondeu ou respondeu algo inesperado."""


@dataclass(frozen=True)
class TierResult:
    label: str
    winners: int
    prize: Decimal


@dataclass(frozen=True)
class DrawResult:
    lottery: str
    contest: int
    date: date | None
    numbers: list[str]
    second_numbers: list[str] | None
    extra_values: list[str]
    tiers: list[TierResult]
    accumulated: bool
    next_contest: int | None
    next_date: date | None
    next_estimate: Decimal
    jackpot: Decimal  # acumulado para o próximo concurso
    collected: Decimal
    location: str
    matches: list[dict] = field(default_factory=list)
    fetched_at: datetime | None = None
    stale: bool = False

    @property
    def extra_label(self) -> str:
        return " e ".join(self.extra_values)

    @property
    def name(self) -> str:
        return catalog.get(self.lottery).name

    def tier(self, label: str) -> TierResult | None:
        for tier in self.tiers:
            if tier.label == label:
                return tier
        return None

    @property
    def total_winners(self) -> int:
        return sum(tier.winners for tier in self.tiers)


def _date(text) -> date | None:
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _clean(text) -> str:
    """Normaliza texto da API: tira bytes nulos e espaços repetidos."""
    if not text:
        return ""
    return re.sub(r"[\s\x00]+", " ", str(text)).strip()


def _decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def parse(payload: dict, fetched_at=None) -> DrawResult:
    """Converte a resposta da Caixa em ``DrawResult``. Levanta ``ResultsUnavailable`` se faltar o essencial."""
    try:
        contest = int(payload["numero"])
        kind = str(payload.get("tipoJogo") or "")
    except (KeyError, TypeError, ValueError) as exc:
        raise ResultsUnavailable("Resposta sem número de concurso.") from exc
    slug = kind.lower().replace("_", "")
    if slug == "loteriafederal":
        slug = "federal"
    if slug not in catalog.LOTTERIES:
        raise ResultsUnavailable(f"Loteria desconhecida na resposta: {kind!r}.")

    numbers = [str(n) for n in payload.get("listaDezenas") or []]
    second = payload.get("listaDezenasSegundoSorteio") or None
    second_numbers = [str(n) for n in second] if second else None

    extra_values: list[str] = []
    # Sem extra, a Caixa manda uma sequência de bytes nulos nesse campo.
    extra_name = _clean(payload.get("nomeTimeCoracaoMesSorte"))
    if payload.get("trevosSorteados"):
        extra_values = [str(t) for t in payload["trevosSorteados"]]
    elif extra_name:
        extra_values = [extra_name]

    tiers = []
    raw_tiers = payload.get("listaRateioPremio") or []
    half = len(raw_tiers) // 2 if second_numbers else None
    for index, item in enumerate(raw_tiers):
        label = str(item.get("descricaoFaixa") or f"Faixa {item.get('faixa')}").strip()
        if half:
            label = f"{'1º' if index < half else '2º'} sorteio: {label}"
        tiers.append(TierResult(label, int(item.get("numeroDeGanhadores") or 0), _decimal(item.get("valorPremio"))))

    matches = []
    for game in payload.get("listaResultadoEquipeEsportiva") or []:
        matches.append(
            {
                "order": game.get("nuSequencial"),
                "home": game.get("nomeEquipeUm"),
                "away": game.get("nomeEquipeDois"),
                "home_goals": game.get("nuGolEquipeUm"),
                "away_goals": game.get("nuGolEquipeDois"),
                "date": game.get("dtJogo"),
            }
        )

    location = _clean(" ".join(
        part for part in (payload.get("localSorteio"), payload.get("nomeMunicipioUFSorteio")) if part
    ))
    return DrawResult(
        lottery=slug,
        contest=contest,
        date=_date(payload.get("dataApuracao")),
        numbers=numbers,
        second_numbers=second_numbers,
        extra_values=extra_values,
        tiers=tiers,
        accumulated=bool(payload.get("acumulado")),
        next_contest=int(payload["numeroConcursoProximo"]) if payload.get("numeroConcursoProximo") else None,
        next_date=_date(payload.get("dataProximoConcurso")),
        next_estimate=_decimal(payload.get("valorEstimadoProximoConcurso")),
        jackpot=_decimal(payload.get("valorAcumuladoProximoConcurso")),
        collected=_decimal(payload.get("valorArrecadado")),
        location=location,
        matches=sorted(matches, key=lambda m: m["order"] or 0),
        fetched_at=fetched_at,
    )


def _download(url: str) -> dict:
    """Baixa e decodifica o JSON. Isolado para ser substituído nos testes."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ResultsUnavailable(f"Falha ao consultar {url}: {exc}") from exc


def _url(slug: str, contest: int | None = None) -> str:
    url = API_URL.format(slug=catalog.get(slug).api_slug)
    return f"{url}/{contest}" if contest else url


def store(payload: dict) -> DrawResult:
    """Valida a resposta e a guarda no banco; devolve o resultado já interpretado."""
    result = parse(payload)
    snapshot, _ = ResultSnapshot.objects.update_or_create(
        lottery=result.lottery, contest=result.contest, defaults={"payload": payload}
    )
    return replace(result, fetched_at=snapshot.fetched_at)


def _today() -> date:
    return date.today()


def _download_latest(slug: str) -> dict:
    """Baixa o último concurso; se o "próximo" já deveria ter saído, tenta pegá-lo também.

    O endpoint sem número às vezes fica um concurso atrasado no dia do sorteio.
    """
    payload = _download(_url(slug))
    next_contest = payload.get("numeroConcursoProximo")
    next_date = _date(payload.get("dataProximoConcurso"))
    if next_contest and next_date and next_date <= _today():
        try:
            newer = _download(_url(slug, int(next_contest)))
        except ResultsUnavailable:
            return payload
        if str(newer.get("numero")) == str(next_contest) and newer.get("listaDezenas"):
            return newer
    return payload


def fetch(slug: str, contest: int | None = None) -> DrawResult:
    """Consulta a API e guarda a resposta. Levanta ``ResultsUnavailable``."""
    if contest is None:
        return store(_download_latest(slug))
    return store(_download(_url(slug, contest)))


def _from_snapshot(snapshot: ResultSnapshot | None, stale=True) -> DrawResult | None:
    if snapshot is None:
        return None
    try:
        return replace(parse(snapshot.payload), fetched_at=snapshot.fetched_at, stale=stale)
    except ResultsUnavailable:
        return None


def known_latest(slug: str) -> DrawResult | None:
    """Último concurso guardado no banco, sem consultar a rede."""
    snapshot = ResultSnapshot.objects.filter(lottery=slug).order_by("-contest").first()
    stale = snapshot is None or timezone.now() - snapshot.fetched_at > timedelta(seconds=CACHE_TTL)
    return _from_snapshot(snapshot, stale=stale)


def known_latest_all(slugs) -> dict[str, DrawResult | None]:
    """Últimos resultados conhecidos, sem consultar a rede."""
    return {slug: known_latest(slug) for slug in slugs}


def latest(slug: str) -> DrawResult | None:
    """Último resultado: cache, depois API, depois último conhecido no banco (``stale``)."""
    key = f"loterias:ultimo:{slug}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    if not cache.get(f"loterias:falha:{slug}"):
        try:
            result = fetch(slug)
        except ResultsUnavailable as exc:
            log.warning("Resultado indisponível para %s: %s", slug, exc)
            cache.set(f"loterias:falha:{slug}", True, FAILURE_TTL)
        else:
            cache.set(key, result, CACHE_TTL)
            return result
    snapshot = ResultSnapshot.objects.filter(lottery=slug).order_by("-contest").first()
    return _from_snapshot(snapshot, stale=True)


def latest_all(slugs) -> dict[str, DrawResult | None]:
    """Último resultado de várias loterias, baixando em paralelo o que não está em cache."""
    slugs = list(slugs)
    results: dict[str, DrawResult | None] = {}
    pending = []
    for slug in slugs:
        cached = cache.get(f"loterias:ultimo:{slug}")
        if cached is not None:
            results[slug] = cached
        elif cache.get(f"loterias:falha:{slug}"):
            results[slug] = known_latest(slug)
        else:
            pending.append(slug)

    def download(slug):
        try:
            return _download_latest(slug)
        except ResultsUnavailable as exc:
            log.warning("Resultado indisponível para %s: %s", slug, exc)
            return None

    if pending:
        with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
            payloads = dict(zip(pending, pool.map(download, pending)))
        for slug in pending:
            payload = payloads[slug]
            result = None
            if payload is not None:
                try:
                    result = store(payload)
                except ResultsUnavailable as exc:
                    log.warning("Resposta inválida para %s: %s", slug, exc)
            if result is None:
                cache.set(f"loterias:falha:{slug}", True, FAILURE_TTL)
                snapshot = ResultSnapshot.objects.filter(lottery=slug).order_by("-contest").first()
                result = _from_snapshot(snapshot, stale=True)
            else:
                cache.set(f"loterias:ultimo:{slug}", result, CACHE_TTL)
            results[slug] = result
    return {slug: results.get(slug) for slug in slugs}


def for_contest(slug: str, contest: int) -> DrawResult | None:
    """Resultado local de um concurso; atualizações externas são feitas pelo comando agendado."""
    snapshot = ResultSnapshot.objects.filter(lottery=slug, contest=contest).first()
    if snapshot is not None:
        return _from_snapshot(snapshot, stale=False)
    return None
