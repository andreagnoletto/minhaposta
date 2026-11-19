# MINHAPOSTA.COM.BR — Simulador educativo de apostas (Django)

Nome anterior do projeto: Jogo do Bixo (renomeado em 11/10/2026; a pasta e os arquivos mantêm `jogobixo`).

Data: 2026-10-11

## Objetivo

Aplicação web em Django, para fins educativos, que simula o jogo do bicho,
roleta, caça-níquel e dado, usando **fichas fictícias** (sem dinheiro real,
sem pagamentos). O propósito é mostrar na prática como esses jogos funcionam
e, principalmente, **por que a banca sempre ganha**: cada jogo expõe sua
probabilidade real, o pagamento oferecido, o pagamento justo e a vantagem da
casa, e o painel do usuário mostra o resultado acumulado das próprias apostas.

## Premissas assumidas (ninguém disponível para confirmar)

- "Educativo" = ensinar as regras e a matemática (probabilidade, valor
  esperado, vantagem da casa). Também serve como projeto de estudo de Django.
- Nenhuma integração de pagamento. Moeda: "fichas" (F$). Recargas ilimitadas,
  mas contadas e exibidas (quantas vezes o usuário precisou recarregar).
- Interface em português do Brasil; identificadores de código em inglês,
  preservando termos do domínio (milhar, centena, dezena, grupo, extração).
- Estrutura gerada pela CLI do Django (`startproject`, `startapp`), conforme
  pedido do usuário. Banco SQLite. Sem DRF, sem framework JS: templates
  server-side com CSS próprio e JS mínimo.
- Sem repositório git (o usuário não pediu).

## Jogos e regras

### Jogo do bicho

- 25 grupos (bichos), cada um com 4 dezenas: grupo *n* cobre as dezenas
  4n-3 .. 4n; a dezena 00 vale 100 e pertence ao grupo 25 (Vaca).
- Extração: 5 prêmios, cada um uma milhar de 0000 a 9999. "Cabeça" = 1º prêmio.
- Modalidades e pagamento na cabeça: Grupo 18x, Dezena 60x, Centena 600x,
  Milhar 4000x. Posição "1º ao 5º" (cercado): paga `multiplicador / 5` por
  prêmio acertado, somando os acertos (vantagem da casa idêntica à cabeça).
- Fluxo: apostas entram na extração aberta; qualquer usuário logado pode
  acionar "Sortear agora" (ou o comando `sortear`), o que encerra a extração,
  liquida as apostas pendentes, paga os vencedores e abre a próxima.

| Modalidade | Probabilidade | Paga | Justo | Retorno esperado | Vantagem da banca |
|---|---|---|---|---|---|
| Grupo | 4% | 18x | 25x | 72% | 28% |
| Dezena | 1% | 60x | 100x | 60% | 40% |
| Centena | 0,1% | 600x | 1000x | 60% | 40% |
| Milhar | 0,01% | 4000x | 10000x | 40% | 60% |

### Roleta (europeia, 37 casas)

Uma aposta por giro: número (36x), vermelho/preto, par/ímpar, baixo/alto (2x),
dúzia ou coluna (3x). Vantagem da casa 2,70% em todas.

### Caça-níquel

3 rolos de 20 símbolos com pesos; tabela de prêmios para trincas e para
exatamente duas cerejas. O RTP é calculado exatamente a partir dos rolos
(enumeração das 8000 combinações) e exibido na página.

### Dado

Acerte a face de um dado de 6 lados; paga 5x (justo seria 6x). Vantagem 16,7%.

## Arquitetura

Projeto `config` + apps:

- `core` — página inicial, cadastro, templates base e CSS.
- `wallet` — `Wallet` (saldo) e `Transaction` (livro-razão: bônus, aposta,
  prêmio, com jogo e saldo posterior). Serviços `debit`/`credit` atômicos.
  Views: extrato, recarga, painel de estatísticas (gráfico SVG do saldo).
- `bicho` — tabela estática dos 25 bichos, `Draw` (extração) e `Bet`;
  serviços de liquidação; comando `sortear`.
- `casino` — motores puros (roleta, caça-níquel, dado) + `CasinoRound`
  (jogo, aposta, prêmio, detalhes JSON).
- `learn` — páginas educativas (regras, probabilidade, vantagem da casa,
  falácias, aspectos legais e jogo responsável) e simulador Monte Carlo
  (N apostas automáticas sem mexer na carteira).

Toda movimentação de fichas passa pelos serviços de `wallet`, dentro de
`transaction.atomic()`. Estatísticas derivam do livro-razão.

## Erros

- Saldo insuficiente, aposta acima do máximo (500 fichas) ou palpite
  inválido: erro de formulário, nada é debitado.
- Sorteio sem apostas pendentes: permitido (apenas gera a extração).

## Testes

`manage.py test`: mapeamento dezena→grupo, cálculo de prêmio por modalidade e
posição, liquidação de extração (pagamento e saldo), motores de roleta /
caça-níquel / dado (pagamentos, RTP), serviços de carteira (débito atômico,
saldo insuficiente), fumaça das views principais. Desde 02/11/2026, o pacote
`e2e/` acrescenta testes de navegador (Playwright + `StaticLiveServerTestCase`),
pulados automaticamente quando o Playwright não está instalado.

## Adendo (11/10/2026): seção Loterias da Caixa

Pedido: "coletar informações sobre loterias no Brasil, investigar APIs de
resultados, criar páginas orientativas e abrir possibilidade de apostar
nesses jogos legalmente se possível".

Pesquisa:

- Resultados: o portal da Caixa consome `https://servicebus2.caixa.gov.br/
  portaldeloterias/api/<loteria>[/<concurso>]` (JSON; não documentado
  oficialmente; concursos inexistentes devolvem HTTP 500). Como o endpoint
  não é uma API pública documentada, seu formato pode mudar. APIs
  comunitárias (loteriascaixa-api no Heroku, api.guidi.dev.br) são apenas
  espelhos desse endpoint e podem bloquear IPs fora do Brasil; não usar.
- Regras, preços e calendário: páginas oficiais em loterias.caixa.gov.br
  (reajuste de julho/2025: Mega-Sena R$ 6, Lotofácil R$ 3,50, Quina R$ 3,
  Dupla Sena R$ 3, Super Sete R$ 3, Loteca R$ 4). Em 2026 os sorteios de
  sábado passaram para domingo às 11h.
- Legal: loteria é serviço público da União (Decreto-Lei 204/1967; Lei
  13.756/2018). Só a Caixa vende apostas (lotéricas, Loterias Online, app,
  Internet Banking); a Caixa não reconhece bolões ou intermediação de
  terceiros e já acionou o MPF e a Justiça contra sites e influenciadores.
  Mínimo on-line reduzido de R$ 20 para R$ 2,50 em dezembro de 2025; 18+ e
  CPF obrigatórios. Portanto **o site não pode vender nem intermediar
  apostas**: oferece os canais oficiais e um bilhete de treino com fichas.

Design do app `loterias` (criado com `startapp`):

- `catalog.py`: dataclasses `Lottery`/`Tier`/`Extra` com as 11 loterias,
  faixas com o mesmo rótulo da API (`"6 acertos"`, `"Mês da Sorte"`,
  `"6 acertos + 2 trevos"`, `"1º sorteio: 3 acertos"`).
- `odds.py`: hipergeométrica (números), binomial (Super Sete), extra
  independente; testes comparam com a tabela oficial (1 em N).
- `results.py`: `parse` → `DrawResult`; `latest` consulta cache/API e usa o
  último `ResultSnapshot` como fallback; falhas ficam em cache por 90 s;
  `latest_all` baixa em paralelo (threads só para HTTP, banco na thread
  principal). As páginas usam snapshots locais, sem consulta HTTP durante a
  requisição. `for_contest` só retorna o snapshot exato guardado para conferir
  um bilhete.
- `services.py`: `validate_pick`, `surpresinha`, `score` (acertos, 2º
  sorteio, extra, faixas e prêmio = rateio real; faixa máxima sem ganhador
  real paga o acumulado), `place_ticket` (débito = preço real) e
  `settle_pending` (crédito do rateio). Timemania ignora o time do coração.
- Páginas: `/loterias/` (cartões com último resultado), `/loterias/<slug>/`
  (regras, chances, rateio, volante de treino, meus bilhetes),
  `/loterias/como-apostar/` (canais oficiais, requisitos, impostos, golpes,
  bets e loterias estaduais). Loteria Federal e Loteca são só orientativas.

## Adendo (25/10/2026): operação segura e atualização dos resultados

Implementação:

- Configuração de produção em `config/settings.py`: `DJANGO_SECRET_KEY`,
  `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_EMAIL_BACKEND`,
  `DJANGO_SECURE_SSL_REDIRECT` e `DJANGO_SECURE_HSTS_SECONDS` são lidos do
  ambiente. A aplicação falha ao iniciar com `DEBUG=False` se
  `DJANGO_SECRET_KEY` não estiver definida. Em produção, HTTPS e cookies
  seguros são o padrão; HSTS fica desligado até receber um valor positivo.
  Quando ativo, `SECURE_HSTS_INCLUDE_SUBDOMAINS` e `SECURE_HSTS_PRELOAD`
  também ficam ativos.
- `loterias.views` lê snapshots locais. O comando `atualizar_loterias` é o
  responsável por buscar novos resultados e também busca snapshots exatos
  para concursos já encerrados que ainda tenham bilhetes pendentes. Portanto,
  a atualização deve ser agendada fora das requisições web.
- `for_contest` não consulta a rede: retorna somente o snapshot guardado para
  aquele concurso. Sem o snapshot exato, o bilhete continua pendente até uma
  atualização bem-sucedida.
- `settle` usa `select_for_update()` e verifica novamente o estado pendente
  dentro da transação antes de registrar o resultado e creditar eventual
  prêmio. A liquidação repetida não deve criar outro crédito. A rotina de
  apostas e sorteios do bicho também bloqueia a extração aberta antes de usá-la,
  serializando o acesso ao sorteio.
- `config/settings.py` agora exige uma chave definida no ambiente de produção;
  `casino/migrations/0002_alter_casinoround_game.py` registra a opção
  `LOTERIA` em `CasinoRound.game`.

Verificação em 25/10/2026:

- `python manage.py test`: 122 testes passaram.
- `python manage.py check`: sem problemas.
- `python manage.py makemigrations --check --dry-run`: nenhuma migração
  pendente.
- `python manage.py check --deploy`, com variáveis temporárias de produção:
  sem avisos.

Operação pendente: definir as variáveis reais no ambiente de implantação e
agendar `python manage.py atualizar_loterias` (por exemplo, a cada 10 minutos).
PostgreSQL permanece como possível evolução; o projeto ainda usa SQLite.

## Adendo (02/11/2026): revisão de UX e testes de navegador

Revisão manual em Chromium (1170 px e 375 px) percorrendo cadastro → bicho →
sorteio → roleta → Mega-Sena → carteira. Achados corrigidos:

- Roleta e caça-níquel: o `json_script` com os dados da roda/rolos ficava
  dentro da `<section aria-live>`, então leitores de tela anunciavam o JSON
  antes do resultado. Movido para fora da região ao vivo. Os botões da mesa
  ganharam `aria-label="N, cor"`.
- Bicho: após "Sortear agora", a página voltava ao topo e o poste ficava a
  ~2,5 telas de distância. O redirecionamento passou a apontar para `#poste`;
  a seção recebeu `id`, `tabindex="-1"` e recebe foco quando a animação
  começa.
- Volante das loterias: era possível marcar mais números que o permitido e o
  erro do servidor ficava fora da tela. O JavaScript agora desabilita as casas
  restantes ao completar a marcação (contador fica verde; vermelho se
  exceder), e, quando o servidor devolve erro, o formulário `#bilhete` é
  rolado para a tela, recebe foco e a lista de erros tem `role="alert"`.
- Carteira e caça-níquel: duas tabelas sem o wrapper `.tabela-rolagem`
  causavam rolagem horizontal da página em 375 px. Envolvidas.

Achados registrados, não corrigidos nesta entrega: cabeçalho + aviso ocupam
~49% da tela em 375 px (candidato a cabeçalho compacto); links da navegação
com 29 px de altura (abaixo dos 44 px recomendados para toque).

Testes de navegador (`e2e/`): classe base `PlaywrightTestCase` sobre
`StaticLiveServerTestCase` (Chromium headless, `reduced_motion` por padrão,
login reaproveitando a sessão do `Client`, falha se houver `pageerror`).
Cenários: cadastro → aposta → sorteio com poste em tela e focado; roleta com
animação e texto acessível da região ao vivo; volante bloqueando o 7º número
e erro do servidor focado; nenhuma rolagem horizontal em 375 px nas páginas
principais; tabelas sempre dentro de `.tabela-rolagem`; um `h1`, `main#conteudo`
e link "pular" em cada página. Dependências em `requirements-dev.txt`
(`playwright`); sem elas a suíte é pulada.

Verificação em 02/11/2026: `python manage.py test` → 132 testes (125 unitários
+ 7 e2e) passaram; com o Playwright bloqueado, os 7 e2e são pulados e a suíte
continua verde.

## Adendo (19/11/2026): deploy em contêiner

Decisão: publicar no Coolify, em servidor próprio, mantendo e-mail e DNS no
Plesk. No Plesk Obsidian o caminho para este app seria a extensão Docker, que
roda imagens prontas (sem build a partir do Git) e cujos contêineres não
entram em backup nem migração do Plesk; o Coolify dá deploy por push, TLS,
volume persistente e tarefas agendadas dentro do contêiner. Em 19/11/2026 o
domínio ainda respondia pelos servidores `a.auto.dns.br` e `b.auto.dns.br`
(DNS do Registro.br), sem registro A.

Implementação:

- `Dockerfile`: `python:3.12-slim`, gunicorn (`WEB_CONCURRENCY` workers),
  `collectstatic` no build, usuário `app` sem privilégios, SQLite em `/data`,
  `migrate` na inicialização e `HEALTHCHECK` em `/healthz`.
- `config/settings.py`: `DJANGO_DB_PATH`; `STATIC_ROOT` e WhiteNoise (nomes
  com hash e compressão quando `DEBUG=False`); `DJANGO_TRUST_PROXY_HEADERS`
  ativa `SECURE_PROXY_SSL_HEADER`, sem o qual o redirecionamento para HTTPS
  entra em laço atrás do proxy; `LOGGING` no console, porque com
  `DEBUG=False` o Django só enviaria os erros por e-mail.
- `core/middleware.py`: `/healthz` respondido antes de `ALLOWED_HOSTS` e do
  redirecionamento, para a sonda local do contêiner.
- Correção: o adendo de 25/10 trocou `MAILERS` por `EMAIL_BACKEND` com base
  no Django 6.0.3 que estava instalado localmente. No Django 6.1, exigido
  pelo `requirements.txt`, `EMAIL_BACKEND` é que está obsoleto. `MAILERS` foi
  restaurado (o `BACKEND` continua vindo de `DJANGO_EMAIL_BACKEND`) e o
  ambiente local passou a usar Django 6.1.3.
- Agendamento recomendado de `atualizar_loterias`: a cada 5 minutos. Com 10,
  a cópia local passa do limite de 10 minutos por alguns segundos a cada
  ciclo e a página exibe o aviso de desatualizada.

Verificação em 19/11/2026: imagem construída e executada localmente com
volume nomeado, simulando o proxy (`X-Forwarded-Proto: https`): HTTP puro →
301 para HTTPS; via proxy → 200; host desconhecido → 400; estáticos com hash,
gzip e cache imutável; cadastro com CSRF e cookies `Secure`; `Origin` de outro
site → 403; `atualizar_loterias` por `docker exec` gravou snapshots; usuário e
snapshots preservados após recriar o contêiner; contêiner `healthy`.
`python manage.py test` → 133 testes sob Django 6.1.3, sem avisos de
obsolescência.

Não verificado: se a API da Caixa aceita requisições do servidor que vier a
ser contratado (o teste acima partiu da máquina de desenvolvimento).

Pendência conhecida: sob Django 6.1, `python manage.py check --deploy` acusa
`mail.E001`, porque o backend de e-mail padrão é o de console. Não impede a
inicialização e o site não envia e-mail hoje (o cadastro não pede endereço).
Se passar a enviar (por exemplo, recuperação de senha), será preciso
configurar um mailer SMTP em `MAILERS`; o resultado "sem avisos" registrado em
25/10 valia para o Django 6.0.3.
