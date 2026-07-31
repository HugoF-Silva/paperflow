# Notas do Autor
O README.md foi gerado por IA — exceto as notas do autor.

Em 2026-07, 
- [x] há ainda apenas 1 plugin (`Academia Perks`) neste marketplace `paperflow`.
- [x] Há ainda apenas duas skills (`/venue-matcher` e `/converter`) neste `Academia Perks` plugin.
- [x] `/venue-matcher` encontra venues com bom fit pro paper — e é o passo prévio ao `/converter`.
- [x] `/converter` é a sequência lógica do `/venue-matcher` — adequa o layout do paper pro template LaTeX da venue apropariada.
- [x] Pode ser executado em batch ou paper por paper.
- [x] Suporta apenas conversão pra LaTeX.
- [x] Depende da uma chave de API da OpenAI.

## Ressalvas

As SKILLS foram arquitetadas para serem executadas em websites (e.g. claude.ai / chatgpt.com) mas eles não as suportavam.
É possível executá-las no aplicativo baixado (e,g. Claude Desktop / Codex Desktop), mas podem haver falhas imprevisíveis 
pois não são executadas num ambiente isolado já que tais aplicativos — por padrão — usam o seu computador como o ambiente 
para executar as SKILLS; o que pode vir a ser um problema já que o que funciona no ambiente do seu computador não 
significa que é o que funciona no ambiente do computador do autor.

Caso não funcione no seu computador, recomenda-se:
- Um programador para resolver a situação, ou
- Pedir pra alguma IA te ajudar a executar pelo Makefile, já que os comandos deste isolam o ambiente de execução.

Se você prefere utilizar esse plugin através de um produto digital baseado em agentes de IA, 
você precisará de ao menos uma conta no GitHub e recomendo que tenha Claude Desktop instalado na sua máquina.
Você precisará de acesso ao modo Claude Code (2026-07 isso exige plano pago).

> Isso se dá pelo fato de que essa skill depende de uma linha de comando a qual pode levar horas de execução a depender da quantidade de papers ou do processamento
> da máquina, e precisa rodar em segundo plano; algo que você só conseguirá numa máquina a qual você tem autonomia pra definir isso.
> Sites baseados em IA (e.g. claude.ai, chatgpt.com) normalmente não te dão essa autonomia e por padrão não permitem que uma execução de um comando continue por tanto tempo.

### 🚨 Cuidado: o caminho mais curto não é o que você pensa!
Esse é claramente um tipo de aplicação que precisa ser supervisionada por alguém que sabe tudo que a venue demanda como obrigatório.

Não é só "colocar pra rodar e largar" na expectativa de que todos os resultados sairão sempre coerentes; ao menos não no estado atual.
#### ✅ A conversão até funciona com relativa consistência, 🚫 mas a automatização tem dificuldade em julgar qual template ela deveria converter o paper quando não é explicitamente fornecido como arquivo 👎🏻
Sem discernimento de um humano, há risco de deixar passar batido julgamentos e premissas infundadas do agente as quais:
* 🅰️ ou levaram à converter um paper para uma venue que nunca o aceitaria independente,
* 🅱️ ou levaram à converter um paper para um template que não é o qual a venue espera,

Independente se 🅰️ ou 🅱️:
* definitivamente levará o paper a ser rejeitado, e contribui pra você perder tempo e energia atoa.

O caminho "feliz" mais curto com a versão atual da automatização é: 
1. analisar os resultados do agente, 
2. entender como o sistema funciona, 
3. ver o que a venue alvo demanda como obrigatório e ver se o resultado atendeu todos os requisitos,
4. usar apenas resultados que estão em conformidade com o que a venue aponta como obrigatório,
5. executar a automatização isoladamente para papers que levaram a resultados enganadores 
   * _tendo bom senso sobre quando é hora de parar de insistir, "pegar na mão" do agente e facilitar pra ele_
6. entregar o template de "mão beijada" pro agente quando possível e executar o `/converter` individualmente,
7. e complementar qualquer informação da etapa de submissão que a venue exige mas está fora do escopo do agente 
   * _(e.g. cover letters, submeter de fato com devidas infos sobre autores, monitorar emails atrelados às avaliações, etc)_

## Como add o plugin no seu Claude?

#### Fig. 1
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/b77a8580-13e0-4f17-980c-7e99cbd48073" />

Abra o gerenciador de plugins.

#### Fig. 2
<img width="320" height="170" alt="image" src="https://github.com/user-attachments/assets/2ef6d192-56ea-4733-9be6-9e5097a1ec77" />

Adicione o Marketplace deste repositório.

#### Fig. 3
<img width="320" height="165" alt="image" src="https://github.com/user-attachments/assets/90802337-45d4-4dc2-a781-7eba737903a9" />

Vamos colocar este repositório.

#### Fig. 4
<img width="320" height="168" alt="image" src="https://github.com/user-attachments/assets/bcbeab91-f476-4513-89db-58af1d952a31" />

Escreva `<owner>/<repo>` da seguinte forma: `HugoF-Silva/paperflow`

* Se essa é a sua 1ª vez, talvez o Claude peça para conectar com sua conta do GitHub. Se este for o caso, prossiga com a conexão e volte aqui.
* Talvez conectar com o GitHub pela 1ª vez exija que você reinicie o Claude Desktop para sincronizá-lo com seu recem conectado GitHub. Se este for o caso, reinicie e refaça os passos até então.

#### Fig. 5
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/f57212a7-8377-4ac2-8d6a-046734a8b7bd" />

Selecione o repositório e aperte `sync` para sincronizar com o marketplace daqui.

#### Fig. 6
<img width="320" height="168" alt="image" src="https://github.com/user-attachments/assets/b7dc152d-cff6-445e-ba15-53ea9fcb68fa" />

Meu Claude tá com um bug que aparece os plugins duplicados. Talvez isso aconteça com o seu também, não se assuste, só há 1 plugin `Academia Perks` no marketplace `paperflow`.

Você consegue voltar para essa janela a qual foi redirecionado a qualquer momento através de:

<img width="310" height="148" alt="image" src="https://github.com/user-attachments/assets/bef33e09-5a14-452f-a326-7607581bfdd3" />

Depois é só apertar em `Code` da Fig. 6

#### Fig. 7
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/99f62e8e-11e7-4a7e-bc21-d2b3c4d5f4d6" />

Adicione o plugin.

#### Fig. 8
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/d1a3fb74-f778-4bb9-9585-828db927b5f2" />

Abra o gerenciador de plugin novamente da Fig. 1

Academia perks deve estar na lista. Clique.

#### Fig. 9 (prints em ordem de leitura ocidental)

<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/967963c2-f0f4-4420-bbfa-611f073d0992" />
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/a2f6bdfc-f3be-42e5-9337-4e5024dd2423" />
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/3d6000ab-9a80-4ae3-94a0-9a547fae7908" />
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/19a7cc56-28cb-44b1-9b7a-65fa65a0d8af" />

Garanta que o plugin está atualizado e ativado. 

Sempre que checar se há atualizações de versionamento `x.x.x` pendentes deste repositório, e de fato houver: o botão `Update` será liberado para atualizar.

Recomendo que caso saiba que houve aumento no número da versão, volte na janela da Fig. 6 e cheque as atualizações.

#### Fig. 10
<img width="269" height="195" alt="image" src="https://github.com/user-attachments/assets/317d64cc-2d68-4fa1-ab78-e38224d6abad" />

Recomendo que abra a sessão do Claude em uma pasta a qual tem os papers que irá converter.

## ⚠️ Atenção.:
* Em 2026-07, Codex ainda não está preparado pra usar plugins dessa forma. O plugin ainda não foi publicado por lá e sem um plano business ou enterprise, compartilhar/atualizar plugins "clandestinos" é um processo travado.
* Você não precisa usar pelo Claude, você pode clonar o repo e usar o Makefile embora a curva de aprendizado pode ser mais íngreme neste caso — principalmente se já não tiver configurado uma IDE e um ambiente de programação.
  * Eu não testei o uso desse plugin e nem executei os comandos do Makefile num ambiente que não fosse 
    * `WSL + Docker Container Linux` ou 
    * `WSL + Windows local`; 
  * se você optar por outro ambiente, é por sua conta e risco.


#### 1. Se a UX de plugins do Codex melhorar nos próximos meses e quem mantém esse repositório quiser ajustar o plugin pra rodar liso por lá, saiba que: 
* ⚠️ ambas skills desse plugin instrui o agente leitor a executar um ralph loop por paper,
* ⚠️ e a skill explicitamente instrui que, se o leitor for um modelo da OpenAI, o leitor deve configurar o ralph loop com um agente cujo id do modelo de linguagem usado seja equivalente a identidade de quem configura.
* ⚠️ **traduzindo**: se você tá usando GPT 5.6 Sol, será definido GPT 5.6 Sol pra cada ralph loop; o que pode devorar seus créditos.
* Eu recomendo que o mantenedor altere essa instrução pra sempre definir um modelo mais barato e relativamente eficiente como o "gpt-5.4-mini".
> Se o agente leitor não é um modelo da OpenAI, ele é instruído a definir "gpt-5.4-mini" como fallback.


#### 2. Resultados são gerados dentro da pasta em que o Claude executa o comando atrelado ao programa da skill:
Por default, o Claude executa o comando na pasta em que a sessão foi aberta, 
> mas pode acontecer diferente se o Claude espontaneamente resolver executar o comando dentro de outra pasta.

Então não verá resultados surgindo na pasta que quer a não ser que o Claude execute o comando na pasta do seu interesse; como por exemplo ele executar:
*  `cd <pasta-dos-papers> && <linha-de-comando-do-programa-da-skill>`
*  `<linha-de-comando-do-programa-da-skill>` _(default: executa o comando na pasta utilizada na sessão --> gera resultado na pasta da sessão)_
*  `cd <pasta-do-template> && <linha-de-comando-do-programa-da-skill>`
> Recomendo que mitiguem a imprevisibilidade para melhorar a experiência de uso.


#### 4. Entre os resultados gerados, há:
* Resultados do /venue-matcher:
  * `ranking.md` (um ranking de venues que casam com um paper, em ordem decrescente de fit)
* Resultados do /converter:
  * pacote LaTeX do paper convertido para o template da venue mais apropriada (com `.pdf` já compilado dentro)
* Resultados independentes das skills:
  * `_progress.log` (quantos papers já foram concluídos) e
  * `_execution.log` (o que o agente do ralph loop tá fazendo e falando)


#### 3. O `/venue-matcher` não é possível de ser executado individualmente porque, após finalizar, ele majoritariamente executa o `/converter` imediatamente sem que você peça.
* ⚠️ Então a não ser que você interrompa a execução do `/converter` manualmente, ele será executado.


#### 4. Mas você pode executar o `/converter` indiviudalmente:
* ⚠️ Se você passar uma pasta pro `/converter` com mais de um paper, ele tem alto risco de converter o paper errado.
* O `/converter` foi propositalmente desenhado para ser usado com 1 paper na pasta quando ele é utilizado individualmente.


#### 5. Executar o `/venue-matcher` pra `X` papers não garante encontrar venue pra todos:
* Pode ser que não tem venue boa aberta pra submeter o paper ou o agente não encontrou.


#### 6. Encontrar venue pra quaisquer papers não garante que o `/venue-matcher` ou o `/converter` encontre URL de template LaTeX pra todos:
* Pode ser que as venues encontradas não aceitam submissão usando LaTeX.
* ⚠️ A skill só trabalha com conversão de layout se puder usar LaTeX pra formatar o conteúdo do paper.


#### 7. Encontrar templates LaTeX pra quaisquer papers não garante que o `/converter` conseguirá usá-los:
* Pode ser que pra baixar o template de um link, precisa entrar numa conta;
  * ⚠️ o agente não foi construído pra acessar uma conta por você. Você precisará baixar o template e providenciar pro `/converter`
* Pode ser que o template LaTeX tá quebrado.
  * ⚠️ Você precisará trocar de venue, porque eles não forneceram um template funcional.
* Pode ser que acreditaram ser um template LaTeX, mas não era e o `/converter` não achou o certo.
  * ⚠️ Você precisará procurar pelo link adequado ou trocar de venue.

  
#### 8. 💡E é por isso que 
o `/converter` existe separado e, quando utilizado individualmente, foi desenhado especialmente pra ser usado com 1 paper — para resolver **individualmente** cada paper que não foi possível ser convertido:
* Seja porque não foi possível encontrar uma venue com template LaTeX pra ele;
* Ou porque pra obter o template é necessário fazer algo que o `/converter` ainda não é capaz;
* Ou porque o template tá quebrado;
* etc.

💡Assim você consegue `/converter` sem precisar ranquear venues novamente.

## 🚨 Bugs conhecidos 🪳

#### Trava antes de começar (imprevisível — de PC pra PC)
Em um ambiente problemático — por exemplo, com o Python 3.13 sendo executado no Windows, 
um firewall filtrando o tráfego de 127.0.0.1 e sem suporte nativo a socketpair —, o 
Python pode ficar travado em um handshake incompleto de um socketpair pela interface de 
loopback sempre que uma linha com asyncio.run é chamada. 

Trata-se de um problema do ambiente, mas isso é também indício de que a própria SKILL 
— se usada por meio do Claude — poderá ser executada de forma mais estável em um ambiente 
isolado o qual tenha sido arquiteturado especialmente para a execução do Python atrelado a ela. 

Ao usar o Makefile, a execução já ocorre em um container Docker baseado em Linux, portanto, 
até onde sei, esse problema não deveria acontecer se rodar através do Makefile (ao menos 
eu nunca vi acontecer neste caso).

#### Desiste fácil (volta e meia ocorre)
O agente interno de ambas as skills podem deixar de cumprir com o necessário 
pra alcançar o objetivo — i.e. desiste num problema que caso se empenhasse só + um 
pouco, resolvia — embora aconteça de forma mais variada com o `/converter`. Ex. de empecilhos:
* fonte do texto é requisito, mas o `/converter` viu que não tá instalada no PC;
* o `/converter` viu que caminho do arquivo tá no formato do Windows `C:\caminho\do\file` enquanto
o ambiente dele usa o formato POSIX (Linux/Mac) `/mnt/c/caminho/do/file`;
* o `/venue-matcher` não encontrou uma venue que servisse pro paper durante o websearch dele.

⚠️ Atenção: é uma faca de dois gumes — incentivá-lo a dar mais do sangue é também aumentar as chances de 
cruzar pontos que não tem volta. Ex. de riscos: 
* o `/converter` vê que o template tá errado, faz mudanças no template só pra compilar,
mas acaba mexendo no que precisava ser seguido a risca pra submissão ser aceita,
* o `/converter` vê que falta um arquivo essencial pro template funcionar, cria do zero
um que deveria ter sido fornecido pela venue ao invés de gerado (ocorre pra muitos papers).

#### Vai longe demais (volta e meia ocorre)
Se provido ao `/converter` a URL de um template que exige login, o `/converter` pode 
crawlar alguns hyperlinks nas URLs que ele tem acesso, e acabar pensando que o hyperlink 
de um template similar — o qual não precisa de login — é o que ele deveria usar.

⚠️ Atenção: Isso não é de todo ruim, já que que algumas poucas vezes ele — de alguma 
forma — acha o link para download direto do template por mais que tenha restrição de acesso.

#### Usa o template errado (volta e meia ocorre)
O `/converter` fica confuso achando que a URL do template providenciada pelo `/venue-matcher`
é de fato o template da venue que estamos usando de alvo para conversão do paper;

⚠️ Atenção: Alguém poderia pensar que é o `/venue-matcher` o problemático, já que foi ele 
que passou uma URL atrelada a um template que não é nosso alvo e ainda afirmou com toda 
certeza do mundo que era de fato o template correto. 
* Mas esse comportamento é esperado: afinal não é responsabilidade do `/venue-matcher`
achar o template certo para toda e cadavenue,
* O dever dele é outro: ranqueá-las de acordo com as características do paper.
* Na verdade, hoje o dever de verificar e achar o link certo independente do link
entregue estar errado está centrado totalmente no `/converter`.
  * Mas independente, de fato isso tá deixando o `/converter` confuso.

#### Alucinação de ID (ocorre poucas vezes)
O gpt-5.4-mini, atual modelo default para os agentes internos do plugin, as vezes 
erra uma letra no meio do ID. 

A etapa do processo na qual simultaneamente:
* é consideravelmente crítica, e
* há possibilidade do usuário interceder (human-in-the-loop)

é quando ocorre entre o `/venue-matcher` e o `/converter` a repassagem automática das URLs atreladas à venue alvo.
* ⚠️ Pode ser que alguma das URLs tenha um erro de caractére escondido.

Enquanto você não arrumar a causa raiz do erro e nem mudar para um modelo que alucina menos com IDs:
* Você pode corrigir manualmente essas URLs no `/results/ranking.md` (de lá que são pegas).
* É só abrir uma que tá funcionando do top-1 do ranking, e no site dessa achar a outra escrita corretamente (pra que você possa arrumar no ranking.md)
  * em seguida é só rodar o `/converter` de novo.
 
#### Acha que a coversão do paper atende a venue (imprevisível)
Você precisa saber o que a venue pede e como o template deveria ser pra saber se a conversão atendeu ou não.
Pode acontecer mais vezes do que a gente imagina.

Algumas poucas vezes vi acontecendo este caso:
* o `/converter` acha que o paper tem mais que o mínimo de páginas necessário pra ser aceito na venue.
* trata como se o paper fosse normal ao invés de parar a conversão e avisar.
* o `/converter` ignora o fato de que a venue pediu ORCID de todos os autores e não tem ORCID de todos os autores.

#### E alucinações no geral
Exemplo:
* o `/converter` acha que a venue não precisa pagar taxa (provavelmente porque não cruzou com essa info)
* o `/converter` overthinka e pega outro template 

 ---

# Paperflow — Academia Perks

The plugin lives at `src/plugins/academia-perks/`. It is a single shared
payload, with both Codex and Claude Code manifests; there are no longer
provider-specific `academia-perks-openai` or `academia-perks-claude` plugin
copies.

## Install the plugin

### Codex

The repository marketplace at `.agents/plugins/marketplace.json` exposes the
`academia-perks` plugin, whose Codex manifest is
`src/plugins/academia-perks/.codex-plugin/plugin.json`. Add this repository as
a marketplace in Codex, then install **Academia Perks** from that marketplace.

### Claude Code

Claude Code also installs the same plugin from the command line, through the
marketplace at `.claude-plugin/marketplace.json` and its Claude manifest at
`src/plugins/academia-perks/.claude-plugin/plugin.json`:

```bash
claude plugin marketplace add /path/to/paperflow
claude plugin install academia-perks@paperflow
```

For a hosted repository, replace the local path with the repository shorthand
or Git URL supported by Claude Code. See the [Claude Code marketplace
guide](https://code.claude.com/docs/en/plugin-marketplaces) for the supported
source forms.

## Use it

Input and output are two separate directories. The input directory holds the
papers and is never written to; only `.docx` files sitting directly in it are
read, so nested papers and other file types are ignored.

Both CLIs require an explicit `--input-dir`: the Docker harness fixes it at
`src/papers/`, and plugin use points it at the directory the agent was given.
Output always goes to one `results/` root (override with `OUTPUT_DIR`), where
both skills share a single workspace directory per paper — so conversion reuses
the match already made for that paper:

```text
papers/                        # input: flat .docx files, read-only
└── my-paper.docx

results/                       # output
├── _execution.log             # agent execution stream (both skills)
├── _progress.log              # matcher batch progress
├── _converter_progress.log    # converter batch progress
└── my-paper/                  # one workspace per paper, named after its .docx
    ├── ranking.md             # matcher: ranked venues
    ├── downloads/             # converter: template archives fetched from URLs
    ├── extracted_figures/     # converter: figures pulled from the .docx
    ├── conversion-status.md   # converter: terminal state and reason
    └── converted/             # converter: the LaTeX submission tree
        ├── main.tex
        └── main.pdf
```

The agent extracts downloaded archives with shell commands inside the
workspace, then copies the authoritative template from there into `converted/`.
No fixed directory is reserved for the extracted tree.

The bundled inner agents use the OpenAI Agents SDK, and select an
OpenAI-compatible inner-agent model through `VENUE_MATCHER_MODEL` or
`CONVERTER_MODEL`; normal plugin use handles that for the agent.

On Windows, both CLIs refuse to start when a paper's workspace path would
certainly exceed Windows' path limits (260-char MAX_PATH family), naming the
offending papers and the budget instead of failing mid-batch — move the
results root somewhere shallower or shorten the paper filenames, then re-run.

## Develop locally with Docker

The repository's Docker harness runs the shared plugin through an OpenAI outer
agent. Docker Desktop must be running.

```bash
cp ops/.env.example ops/.env
cp ops/.paperflow.local.toml.example ops/.paperflow.local.toml
# Add one or more .docx papers directly under src/papers/
make -C ops run
```

Set `OPENAI_API_KEY` in `ops/.env`. `OPENAI_MODEL` is optional and defaults to
`gpt-5.4-mini`. The Compose service mounts the repository's `src/` directory at
`/app/src`, so inputs come from `src/papers/` and results appear in
`src/results/` on the host. `make -C ops run` starts the matcher-and-converter
workflow with `--api=openai`.

For a standalone conversion, provide exactly one source:

```bash
make -C ops run-converter chosen-venue='Venue A template: https://venue.example/template'
make -C ops run-converter template-path='/app/src/templates/venue-a.zip'
```

`chosen-venue` must identify the venue and include its template URL or
supporting evidence. A `template-path` is a container path; place the template
under the repository's `src/` tree and refer to it as `/app/src/...`.

The harness exposes `MAX_PARALLEL` (default `auto`), `MAX_RALPH` (default `4`),
and `INNER_MAX_TURNS` (minimum/default `50`) as developer controls. Set them in
`ops/.env` only when you need to tune a local run. `make -C ops down` removes
the Compose containers and volumes; `make -C ops prune` additionally runs a
global Docker image/volume prune.

### Current provider boundary

`harness/cli.py` and `harness/outer_agent.py` still contain legacy Anthropic
branches, but this checkout no longer includes the old
`plugins/academia-perks-claude` payload those branches resolve. The supported
Docker harness path is consequently OpenAI-only. This does not affect the
Claude Code marketplace: it installs the shared `academia-perks` plugin above,
whose bundled work is performed with the OpenAI API key supplied for the run.

## How the workflows work

Each inner agent's Ralph loop carries a compact recap into the next pass until
it has a terminal result. The matcher uses one geographic audience scope from
the paper: its sole stated scope, the first if several are stated, or
**International** when none is given. It ranks only venues whose primary
audience fits that scope, and separates currently open venues from those
opening soon.

When conversion is requested after matching, the skills use completed
per-paper results rather than guessing from files. The converter uses Pandoc to
preserve document structure and verifies the generated submission with
Tectonic.
