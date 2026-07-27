# Notas do Autor
O README.md foi gerado por IA — exceto as notas do autor.

Se você prefere utilizar esse plugin através de um produto digital baseado em agentes de IA, 
você precisará de ao menos uma conta no GitHub e recomendo que tenha Claude Desktop instalado na sua máquina.
Você precisará de acesso ao modo Claude Code (2026-07 isso exige plano pago).

> Isso se dá pelo fato de que essa skill depende de uma linha de comando a qual pode levar horas de execução a depender da quantidade de papers ou do processamento
> da máquina, e precisa rodar em segundo plano; algo que você só conseguirá numa máquina a qual você tem autonomia pra definir isso.
> Sites baseados em IA (e.g. claude.ai, chatgpt.com) normalmente não te dão essa autonomia e por padrão não permitem que uma execução de um comando continue por tanto tempo.

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

Meu Claude tá com um bug que aparece os plugins duplicados. Talvez isso aconteça com o seu também, não se assuste, só há 1 plugin `Academia Perks` no parketplace `paperflow`.

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

#### Fig. 9
<img width="320" height="169" alt="image" src="https://github.com/user-attachments/assets/5e6cf76d-b5eb-4c55-b91e-0d9231f21d16" />

Garanta que o plugin está atualizado e ativado. 

Sempre que houver a atualização de versionamento neste repositório (i.e. um novo commit na main), o botão `Update` será liberado para atualizar.

Recomendo que caso saiba de atualização, volte nesta janela e atualize.

#### Fig. 10
<img width="269" height="195" alt="image" src="https://github.com/user-attachments/assets/317d64cc-2d68-4fa1-ab78-e38224d6abad" />

Recomendo que abra a sessão do Claude em uma pasta a qual tem os papers que irá converter.

---

### ⚠️ Atenção.:
* Em 2026-07, Codex ainda não está preparado pra usar plugins dessa forma. O plugin ainda não foi publicado por lá e sem um plano business ou enterprise, compartilhar/atualizar plugins "clandestinos" é um processo travado.
* Você não precisa usar pelo Claude, se você for um dev eu recomendo que você clone o repo e use o Makefile. Se você não tem um ambiente de programação definido na sua máquina, até você conseguir finalmente executar pode ser uma jornada.
* Eu não testei o uso desse plugin e nem executei os comandos do Makefile num ambiente que não fosse `WSL + Docker Container Linux` ou `WSL + Windows local`; se você optar por outro ambiente, é por sua conta e risco.

#### 1. Se e a UX de plugins do Codex melhorar nos próximos meses e quem mantém esse repositório quiser ajustar o plugin pra rodar liso por lá: 
* ⚠️ ambas skills desse plugin instrui o agente leitor a executar um ralph loop por paper,
* ⚠️ e a skill explicitamente instrui que, se o leitor for um modelo da OpenAI, o leitor deve configurar o ralph loop com um agente cujo id do modelo de linguagem usado seja equivalente a identidade de quem configura.
* ⚠️ **traduzindo**: se você tá usando GPT 5.6 Sol, será definido GPT 5.6 Sol pra cada ralph loop; o que pode devorar seus créditos.
* Eu recomendo que o mantenedor altere essa instrução pra sempre definir um modelo mais barato e eficiente como o "gpt-5.4-mini".
> Se não o leitor não é um modelo da OpenAI, a atual instrução é definir "gpt-5.4-mini" como fallback.

#### 2. Resultados são gerados dentro da pasta em que a sua sessão do Claude está aberta; entre os resultados há:
* Resultados do /venue-matcher: ranking.md (um ranking de venues que casam com um paper, em ordem decrescente de fit)
* Resultados do /converter: pacote LaTeX do paper convertido para o template da venue mais apropriada (com pdf já compilado dentro)
* Resultados independentes das skills: _progress.log (quantos papers já foram concluídos) e _execution.log (o que o agente do ralph loop tá fazendo e falando)

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


---


# Paperflow — Academia Perks

Paperflow packages **Academia Perks**, one academic-publishing plugin with two
agent skills:

- **venue-matcher** finds publication venues that fit a `.docx` paper, ranks
  them, separates currently open venues from those opening soon, and records a
  venue-specific LaTeX template URL when it can verify one.
- **converter** turns a `.docx` paper into a venue-oriented LaTeX submission,
  either after matching or from a supplied venue/template source.

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

Claude Code users can use the marketplace at
`.claude-plugin/marketplace.json`, which installs the same plugin through its
Claude manifest at `src/plugins/academia-perks/.claude-plugin/plugin.json`:

```bash
claude plugin marketplace add /path/to/paperflow
claude plugin install academia-perks@paperflow
```

For a hosted repository, replace the local path with the repository shorthand
or Git URL supported by Claude Code. See the [Claude Code marketplace
guide](https://code.claude.com/docs/en/plugin-marketplaces) for the supported
source forms.

## Use it

Ask the agent to find a venue for a paper, match venues in a folder, or convert
a paper using a selected venue or local LaTeX template. The skills accept only
`.docx` files placed directly in the selected input directory; nested papers
and other file types are ignored.

The bundled inner agents use the OpenAI Agents SDK. Therefore, regardless of
whether the outer agent is Codex or Claude Code, a run needs an
`OPENAI_API_KEY`. The skills also select an OpenAI-compatible inner-agent model
through `VENUE_MATCHER_MODEL` or `CONVERTER_MODEL`; normal plugin use handles
that for the agent. Long-running matching and conversion are best run from a
local agent environment rather than a browser-only chat session.

Matching creates a `results/` directory in the outer agent's working directory:

```text
results/
├── _execution.log       # detailed harness/agent execution stream
├── _progress.log        # matcher batch progress
└── <paper-stem>/
    └── ranking.md
```

Conversion writes its per-paper workspace beneath the same results root and
records batch progress in `_converter_progress.log`.

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

The outer agent starts one inner agent per paper. Each inner agent may run a
Ralph loop, carrying a compact recap into the next pass until it has a terminal
result. The matcher uses one geographic audience scope from the paper: its sole
stated scope, the first if several are stated, or **International** when none is
given. It ranks only venues whose primary audience fits that scope.

When conversion is requested after matching, the skills use completed
per-paper results rather than guessing from files. For a single completed
match, the agent asks the user to select from the ranked venues before it
converts. For a standalone conversion, the agent requires one explicit
`chosen-venue` source or one local `template-path` source. The converter uses
Pandoc to preserve document structure and verifies the generated submission
with Tectonic.
