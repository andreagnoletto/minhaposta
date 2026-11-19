# MINHAPOSTA.COM.BR

Simulador educativo, em Django, de jogo do bicho, roleta europeia, caça-níquel
e dado, mais um guia das loterias da Caixa com resultados oficiais. Tudo funciona com **fichas fictícias (F$)**: não há dinheiro real,
pagamentos nem prêmios. O objetivo é mostrar, na prática e com números
calculados pelo próprio código, por que a banca sempre ganha.

> No Brasil, explorar ou realizar o jogo do bicho é contravenção penal
> (art. 58 do Decreto-Lei 3.688/1941). Este projeto existe para ensinar
> probabilidade e os mecanismos das apostas, não para incentivá-las.
> Se o jogo está pesando na sua vida, o CVV atende pelo 188, de graça, 24 h.

## O que tem

- **Jogo do bicho**: tabela dos 25 bichos, apostas em grupo, dezena, centena e
  milhar (na cabeça ou do 1º ao 5º), extrações com cinco prêmios e liquidação
  automática. Qualquer usuário logado pode acionar o sorteio; há também o
  comando `sortear`.
- **Roleta europeia**: todas as apostas comuns, com tabela mostrando que todas
  têm a mesma vantagem da banca (o zero).
- **Caça-níquel**: três rolos abertos; o retorno ao jogador é calculado por
  enumeração exata das 8000 combinações.
- **Dado**: o exemplo mais simples (chance 1 em 6, paga 5x).
- **Resultados encenados**: a roda da roleta gira até a casa sorteada, os
  rolos do caça-níquel param um a um, o dado rola e o poste do bicho revela
  os cinco prêmios dígito a dígito. O sorteio é sempre decidido no servidor;
  o JavaScript só encena a revelação e respeita a preferência "reduzir
  movimento" do sistema (sem JavaScript, o resultado aparece direto).
- **Loterias da Caixa**: catálogo das 11 loterias federais (Mega-Sena, Quina,
  Lotofácil, Lotomania, Dupla Sena, Timemania, Dia de Sorte, Super Sete,
  +Milionária, Loteria Federal e Loteca) com regras, preço, dias de sorteio,
  destinação da arrecadação e a chance de cada faixa calculada por
  combinatória (`loterias/odds.py`, conferida contra a tabela oficial nos
  testes). O comando agendado `atualizar_loterias` consulta a API pública da
  Caixa (`servicebus2.caixa.gov.br/portaldeloterias/api/<loteria>`) e guarda
  os resultados em `ResultSnapshot`; as páginas leem as cópias locais, sem
  depender da API para responder. Cópias antigas continuam disponíveis e são
  identificadas como possivelmente desatualizadas.
  Usuários logados registram um **bilhete de treino** com fichas (custa, em
  F$, o preço real da aposta mínima) que é conferido contra o sorteio real e
  recebe o rateio oficial da faixa; qualquer visitante pode conferir uma
  marcação contra o último concurso. A página "Como apostar de verdade" lista
  os canais oficiais e as regras: só a Caixa vende apostas, este site não
  intermedia nada.
- **Carteira**: saldo, livro-razão, gráfico do saldo, recargas contadas e a
  comparação "teoria × prática" entre o que a matemática previa e o que o
  usuário recebeu.
- **Aprenda**: como funciona o bicho, probabilidade e valor esperado, falácias
  do apostador, lei e jogo responsável, e um simulador Monte Carlo de até
  50 000 apostas com gráfico.

## Rodando

Requer Python 3.12+ e [uv](https://docs.astral.sh/uv/) (ou `pip`).
Para produção, configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False` e
`DJANGO_ALLOWED_HOSTS` no ambiente. Sem uma chave definida, o projeto recusa
iniciar com `DEBUG=False`. Em produção, o redirecionamento HTTPS e os cookies
seguros são ativados por padrão. HSTS fica desativado até definir um valor
positivo para `DJANGO_SECURE_HSTS_SECONDS`; antes disso, confirme HTTPS em
todos os subdomínios, pois `SECURE_HSTS_INCLUDE_SUBDOMAINS` e
`SECURE_HSTS_PRELOAD` também são ativados.

`DJANGO_EMAIL_BACKEND` é opcional e define o `BACKEND` de `MAILERS["default"]`;
por padrão, mensagens de e-mail são escritas no console. O site não envia
e-mail hoje; por usar o backend de console, `manage.py check --deploy` acusa
`mail.E001` no Django 6.1.

```bash
uv venv .venv
uv pip install --python .venv -r requirements.txt

# Windows
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser   # opcional, para o /admin/
.venv\Scripts\python manage.py runserver

# Linux / macOS
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Abra <http://127.0.0.1:8777/> (a porta padrão do `runserver` neste projeto é 8777; passe outra como argumento se precisar), crie uma conta (só usuário e senha) e você
recebe F$ 1000 em fichas fictícias.

Outros comandos:

```bash
python manage.py test        # suíte completa (unitários + e2e, se o Playwright estiver instalado)
python manage.py test e2e    # só os testes de navegador
python manage.py sortear     # encerra a extração aberta e liquida as apostas
python manage.py atualizar_loterias [megasena quina ...]   # baixa os últimos resultados da Caixa
```

Os testes de ponta a ponta em `e2e/` abrem um Chromium headless contra o
`StaticLiveServerTestCase` do Django e cobrem cadastro → aposta → sorteio,
roleta (incluindo o que a região `aria-live` anuncia), volante da Mega-Sena,
ausência de rolagem horizontal em 375 px e marcos básicos de acessibilidade.
Para rodá-los, instale as dependências de desenvolvimento e o navegador:

```bash
uv pip install --python .venv -r requirements-dev.txt
.venv/bin/python -m playwright install chromium   # Windows: .venv\Scripts\python
```

Sem o Playwright, esses testes são pulados em vez de falhar.

Agende `atualizar_loterias` fora das requisições web (por exemplo, a cada
5 minutos via cron/Agendador de Tarefas; uma cópia com mais de 10 minutos é
exibida como possivelmente desatualizada). As páginas mostram os resultados
guardados localmente; o comando também busca snapshots de concursos já
disponíveis necessários para conferir bilhetes pendentes. Sem uma atualização
agendada, resultados novos e a conferência de bilhetes podem demorar. Bilhetes
só são liquidados quando o snapshot exato do concurso está guardado.

## Deploy

O `Dockerfile` gera uma imagem com gunicorn e WhiteNoise que roda como usuário
sem privilégios, aplica as migrações ao iniciar e guarda o SQLite em `/data`.
Ela foi feita para ficar atrás de um proxy que termina o TLS e envia
`X-Forwarded-Proto` (por isso já define `DJANGO_TRUST_PROXY_HEADERS=True`,
além de `DJANGO_DEBUG=False`, `DJANGO_DB_PATH=/data/db.sqlite3` e
`WEB_CONCURRENCY=3`).

No [Coolify](https://coolify.io/), crie a aplicação a partir do repositório
Git com o build pack **Dockerfile** e configure:

| Item | Valor |
|------|-------|
| Porta exposta | `8000` |
| Domínios | `https://minhaposta.com.br` e `https://www.minhaposta.com.br` |
| Variáveis de ambiente | `DJANGO_SECRET_KEY` (longa e aleatória) e `DJANGO_ALLOWED_HOSTS=minhaposta.com.br,www.minhaposta.com.br` |
| Armazenamento persistente | **Volume Mount** com destino `/data` |
| Healthcheck do painel | desativado: vale o `HEALTHCHECK` da imagem, que consulta `/healthz` |
| Tarefa agendada | `python manage.py atualizar_loterias`, frequência `*/5 * * * *` |

- Use *Volume Mount*, não um diretório do servidor: o volume nomeado herda da
  imagem a permissão de escrita do usuário `app`.
- A imagem não traz `curl` nem `wget`, exigidos pelo healthcheck HTTP do
  painel; `/healthz` responde sem passar por `ALLOWED_HOSTS` nem pelo
  redirecionamento para HTTPS, então a sonda funciona por `localhost`.
- Gere a chave com
  `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`.
- Depois de confirmar o HTTPS nos dois domínios, defina
  `DJANGO_SECURE_HSTS_SECONDS` (por exemplo, `31536000`).
- Os dados vivem só no volume `/data`: configure um backup dele.
- Antes de escolher o servidor, confirme que ele alcança a API da Caixa:
  `curl -s -o /dev/null -w '%{http_code}\n' https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena`
  deve devolver `200`.

Para testar a imagem localmente, simulando o proxy:

```bash
docker build -t minhaposta .
docker run --rm -p 8000:8000 -v minhaposta-data:/data \
  -e DJANGO_SECRET_KEY=troque-esta-chave -e DJANGO_ALLOWED_HOSTS=localhost minhaposta
curl -H 'X-Forwarded-Proto: https' http://localhost:8000/
```

## Estrutura

| App      | Responsabilidade                                                      |
|----------|------------------------------------------------------------------------|
| `config` | Settings e rotas do projeto (gerado por `django-admin startproject`).   |
| `core`   | Página inicial, cadastro, template base, CSS, `/healthz` (`middleware.py`). |
| `wallet` | Carteira, livro-razão (`Transaction`), serviços de débito/crédito, painel, extrato, gráfico e análise teoria × prática. |
| `bicho`  | Regras puras (`rules.py`), extrações (`Draw`), apostas (`Bet`), liquidação, comando `sortear`. |
| `casino` | Motores puros (`roulette.py`, `slots.py`, `dice.py`), rodadas (`CasinoRound`), views. |
| `learn`  | Páginas educativas e simulador Monte Carlo (`simulator.py`).            |
| `loterias` | Catálogo (`catalog.py`), probabilidades (`odds.py`), API da Caixa com cache e cópia local (`results.py`), bilhete de treino (`services.py`, `Ticket`), comando `atualizar_loterias`. Amostras reais da API em `loterias/samples/`. |
| `e2e`    | Testes de navegador com Playwright (`base.py` com a classe base, `test_flows.py` com os fluxos). Não é um app Django. |

Regras do projeto:

- Toda movimentação de fichas passa por `wallet.services` dentro de
  `transaction.atomic()`; saldo e livro-razão são gravados na mesma transação (no SQLite, com modo IMMEDIATE para serializar escritas).
- A liquidação de bilhetes de loteria revalida e bloqueia o registro na
  transação para impedir crédito duplicado; apostas e sorteios do bicho
  sincronizam o acesso à extração aberta.
- Os motores de jogo não tocam o banco de dados e são testados isoladamente.
- Toda tabela de probabilidade, pagamento e vantagem da banca exibida no site
  é calculada pelo código dos jogos, nunca digitada à mão.

## Regras dos jogos

| Jogo / aposta              | Chance    | Paga   | Justo  | Fica com a banca |
|----------------------------|-----------|--------|--------|------------------|
| Bicho, grupo               | 1 em 25   | 18x    | 25x    | 28%              |
| Bicho, dezena              | 1 em 100  | 60x    | 100x   | 40%              |
| Bicho, centena             | 1 em 1000 | 600x   | 1000x  | 40%              |
| Bicho, milhar              | 1 em 10000| 4000x  | 10000x | 60%              |
| Roleta, qualquer aposta    | varia     | varia  | varia  | 2,7%             |
| Caça-níquel                | tabela    | tabela | —      | 6,6%             |
| Dado                       | 1 em 6    | 5x     | 6x     | 16,7%            |
| Mega-Sena (Caixa), sena    | 1 em 50 063 860 | rateio | —  | 56,2% (43,79% vira prêmio bruto) |

No bicho, "do 1º ao 5º" paga um quinto do multiplicador por prêmio acertado,
o que mantém a vantagem da banca igual à da aposta na cabeça.

Nas loterias da Caixa, preços, dias de sorteio e faixas foram conferidos nas
páginas oficiais em 11/10/2026 e estão em `loterias/catalog.py`; a API de
resultados não é documentada oficialmente e pode mudar.

## Documentação de projeto

- Especificação: `docs/superpowers/specs/2026-10-11-jogobixo-design.md`
- Plano de implementação: `docs/superpowers/plans/2026-10-11-jogobixo.md`
