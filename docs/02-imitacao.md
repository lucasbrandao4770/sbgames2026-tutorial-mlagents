# Módulo 2: Imitação

## Objetivo

Entender por que ensinar por demonstração complementa o Reinforcement Learning puro. Conhecer Clonagem Comportamental (BC) e GAIL o suficiente para ler as curvas de um treino que combina os dois com PPO.

Este módulo também documenta os três runs de imitação que o TCC treinou sobre o FlappyBird. Eles servem para ler as curvas de BC e GAIL, não para comparar valores com o treino de PPO puro do Módulo 1, em [docs/01-primeiro-agente.md](01-primeiro-agente.md).

## Pré-requisitos

- Ambiente instalado conforme [docs/00-instalacao.md](00-instalacao.md), com o ambiente virtual ativo e o terminal na raiz do repositório.
- O run `ppo1` do Módulo 1, em [docs/01-primeiro-agente.md](01-primeiro-agente.md), para comparar as curvas.
- A pasta `Demos/` na raiz do repositório, com as duas demonstrações do TCC.
- Só para gravar uma demonstração nova: o Caminho A, com o projeto `unity/SBGamesMLAgents` aberto no Editor.

## Por que imitar

A recompensa do FlappyBird é esparsa e binária. É +1 ao passar por um vão de canos, -1 ao bater num cano ou numa parede. Não há recompensa por "quase conseguir", só o resultado. Com uma recompensa assim, RL puro depende de o agente encontrar o primeiro +1 por exploração aleatória. Isso pode ser lento. Também corre o risco de tropeçar num atalho barato que evita o -1 sem resolver a tarefa (veja "Reward hacking" em [docs/01-primeiro-agente.md](01-primeiro-agente.md)).

Imitation Learning ataca os dois problemas. A demonstração humana dá ao agente uma noção inicial do que fazer. A recompensa do jogo continua valendo durante todo o treino. Nos runs do TCC, o peso da imitação cai de um run para o outro, e o reforço assume o resto.

## Gravando demonstrações

No dia, gravar uma demonstração nova é uma demonstração de 2 minutos conduzida pelo instrutor, não uma atividade prática. No projeto do tutorial, o GameObject do Flappy já tem um componente Demonstration Recorder, hoje desligado. `Record` está desmarcado, o nome é `FlappyAgentDemo`, e a pasta é `Assets/FlappyBird/Demos`. `Num Steps To Record` está em 0, sem limite de passos até você parar o Play.

Gravar só é possível no Caminho A, com o Editor aberto:

0. Abra a cena `Assets/FlappyBird/Scenes/mainGame.unity`.
1. No Behavior Parameters do Flappy, mude Behavior Type para Heuristic Only.
2. No Demonstration Recorder, confirme ou troque o nome da demonstração e marque Record.
3. Aperte Play e controle o pássaro com a barra de espaço, a tecla lida em `Heuristic()` dentro de `FlappyAgent.cs`. Teste antes: o jogo também bate asas quando a barra de espaço é solta ou o mouse é clicado, e esses pulos não entram na demonstração.
4. Pare o Play: o arquivo `.demo` aparece na pasta configurada no Demonstration Recorder, `Assets/FlappyBird/Demos`.

O FlappyBird recarrega a cena a cada morte. O Demonstration Recorder é destruído junto e recriado, e cada vida vira um arquivo novo: `FlappyAgentDemo.demo`, `FlappyAgentDemo_0.demo` e assim por diante. Por precaução, salve a cena (Ctrl+S, ou Cmd+S no macOS) depois de mudar Behavior Type e Record, para a configuração valer também depois de cada recarga. O `demo_path` aceita uma pasta, então dá para treinar com todos os arquivos de uma vez. Ao terminar, volte Behavior Type para Default, desmarque Record e salve a cena de novo: com Heuristic Only, o agente ignora o treinador e o treino não acontece. Para treinar da raiz do repositório com a gravação nova, copie os arquivos para a pasta `Demos/` e ajuste o `demo_path` no yaml.

No Caminho B, sem Editor, o tutorial já traz duas demonstrações gravadas na pasta `Demos/` da raiz do repositório, cópias das que estão em `Assets/FlappyBird/Demos`: `Level1FlappyAgentDemo.demo` e `Leve2FlappyAgentDemo.demo`. O nome "Leve2" (sem o "l" de "Level") é um erro de digitação original do projeto, mantido de propósito. As configurações de treino já apontam para esse nome de arquivo.

### O arquivo `.demo`

Um arquivo `.demo` guarda os passos gravados: observações, ações e recompensas de cada decisão do agente, junto com metadados como o número total de passos. Esses metadados aparecem no Inspector do Unity, ao selecionar o arquivo. É esse conteúdo que `behavioral_cloning` e `reward_signals.gail` leem, através da chave `demo_path`, descrita a seguir.

### Boas práticas ao gravar

- Demonstre o comportamento que o agente deve aprender: uma demonstração ruim ou inconsistente ensina o agente a errar do mesmo jeito.
- Grave mais de uma sessão, com variações, para o agente não ficar preso a uma única trajetória.
- Evite gravações longas demais: trechos redundantes só dificultam o treino sem ensinar nada novo.

## Clonagem comportamental (BC)

BC (Behavioral Cloning) é o jeito mais direto de aprender por exemplo. O agente observa uma demonstração e copia a ação passo a passo, como um aprendiz repetindo o que viu. Funciona bem para aprender rápido o básico de uma tarefa. Sozinho, tende a generalizar mal fora do que foi demonstrado, porque o agente nunca é forçado a lidar com situações que não apareceram na gravação.

No arquivo de configuração, BC é a seção `behavioral_cloning`, como no `FlappyBird_run1.yaml`:

```yaml
behavioral_cloning:
  demo_path: Demos/Level1FlappyAgentDemo.demo
  strength: 1.0
```

`demo_path` aponta para o arquivo `.demo` usado como exemplo. O BC não soma recompensa. Ele é uma perda supervisionada extra, e `strength` é a taxa de aprendizado dessa imitação em relação à do PPO. Existe também a chave `steps`, que limita por quantos passos o BC fica ativo, com a taxa caindo até zero nesse período. Os runs do TCC não a definem, então o BC roda pelo treino inteiro.

## GAIL

GAIL, Generative Adversarial Imitation Learning, ensina de um jeito mais indireto. Em vez de copiar a ação exata a cada passo, o agente aprende a se comportar de um jeito que um discriminador não consiga distinguir da demonstração. Isso deixa mais espaço para generalizar para situações fora da demonstração. O custo é um treino mais lento e menos estável que o BC puro.

No arquivo de configuração, GAIL é a seção `gail` dentro de `reward_signals`, também como no `FlappyBird_run1.yaml`:

```yaml
reward_signals:
  gail:
    demo_path: Demos/Level1FlappyAgentDemo.demo
    strength: 0.5
```

As chaves `gamma` e `use_actions` existem no ML-Agents. `gamma` é o desconto do sinal de GAIL ao longo do tempo. `use_actions` decide se o discriminador também olha para as ações tomadas, não só para os estados visitados. Nenhuma das duas aparece definida nos yamls de imitação do FlappyBird, então valem o padrão do treinador.

### BC e GAIL, lado a lado

| | BC | GAIL |
|---|---|---|
| Como aprende | Copia a ação exata da demonstração a cada passo | Aprende um padrão de comportamento que engana um discriminador |
| Velocidade | Mais rápido para pegar o básico | Mais lento, treino adversarial |
| Fora da demonstração | Generaliza pior | Generaliza melhor |

### Por que combinar BC, GAIL e recompensa extrínseca

Os três runs do TCC usam BC, GAIL e a recompensa extrínseca do próprio jogo ao mesmo tempo. GAIL e a recompensa extrínseca entram na recompensa total, cada um com o peso do seu `strength`. O BC atua à parte, como uma perda supervisionada, e o `strength` dele regula a força dessa imitação. BC e GAIL aceleram o começo do treino, porque dão ao agente uma noção inicial do que fazer. A recompensa extrínseca garante que o agente continue melhorando além da demonstração. Por isso o TCC reduz `behavioral_cloning.strength` e `gail.strength` ao longo dos três runs, como na tabela abaixo.

## Os três runs do TCC

O TCC treinou o FlappyBird com IL em três runs encadeados, cada um partindo do checkpoint do anterior com `--initialize-from`. A imitação cai a cada etapa, e a recompensa extrínseca sobe do run1 para o run2:

| Run | Demo | `extrinsic.strength` | `gail.strength` | `behavioral_cloning.strength` |
|---|---|---|---|---|
| run1 | `Level1FlappyAgentDemo.demo` | 0.1 | 0.5 | 1.0 |
| run2 | `Leve2FlappyAgentDemo.demo` | 1.0 | 0.4 | 0.4 |
| run3 | `Leve2FlappyAgentDemo.demo` | 1.0 | 0.1 | 0.1 |

Os três usam `max_steps: 50000` e `time_horizon: 200`, iguais ao `FlappyBird_ppo.yaml`. O run3 reaproveita a mesma demonstração do run2, `Leve2FlappyAgentDemo.demo`. Não existe um terceiro arquivo `.demo` no projeto.

No TCC original, run1 e run2 rodaram numa versão do jogo onde bater não encerrava o episódio, e os episódios sempre chegavam a 999 passos. Run3 já rodou com a regra atual, onde bater mata, e os episódios chegaram a cerca de 220 passos no fim do run (veja "Currículo por níveis" em [docs/01-primeiro-agente.md](01-primeiro-agente.md)). No build do tutorial, ao contrário, a regra do jogo é única e fixa. De um run para outro, só mudam os pesos de `extrinsic`, `gail` e `behavioral_cloning` e a demonstração usada.

O foco de cada run muda ao longo da cadeia. O run1 usa pesado o Imitation Learning, via demonstração gravada. O run2 busca um equilíbrio entre imitação e reforço. O run3 passa o foco por completo para o Reinforcement Learning, embora BC e GAIL continuem ativos, com `strength` 0.1.

## Treinando com imitação

Esta parte é a variante opcional do módulo. O teste do arquivo `.demo` contra o build, feito em 24/09, passou: o comando abaixo treina, exporta o ONNX e mostra as tags de BC e GAIL no TensorBoard. Se a variante entrar no dia, BC e GAIL também viram opções no menu do desafio do Módulo 3. O instrutor avisa às 11h00 se a variante vale.

No Windows:

```bash
mlagents-learn python/configs/imitation/FlappyBird_run1.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=il1 --no-graphics
```

No macOS:

```bash
mlagents-learn python/configs/imitation/FlappyBird_run1.yaml --env=builds/FlappyBird.app --run-id=il1 --no-graphics
```

Rode este comando da raiz do repositório. O `demo_path` dentro do yaml é relativo ao diretório de trabalho (`Demos/Level1FlappyAgentDemo.demo`). Ele só resolve certo a partir da raiz, onde fica a pasta `Demos/`. Num único run de teste em 24/09, na máquina de referência, contra o build e com `--no-graphics`, os 50 mil passos levaram 92 segundos.

O treinador carrega a demonstração logo depois de conectar ao build, quando cria o treinador do `FlappyAgent`. Se o arquivo `.demo` não for encontrado, ou não bater com as observações e ações do agente, o comando falha nos primeiros segundos, com o build já aberto.

Nesse run de teste, a configuração do run1 fechou com recompensa média de -0,34. Na mesma máquina, três runs de PPO puro fecharam entre +2,3 e +6,6, com o mesmo número de passos. Isso não é uma falha da imitação: é o ponto pedagógico. Com só 50 mil passos, e um discriminador ainda aprendendo, BC e GAIL não bateram o PPO puro nesse teste. Uma curva completa de BC e GAIL precisa de mais passos e mais ajuste do que cabe no orçamento de tempo do tutorial.

Em casa, dá para refazer a cadeia completa do TCC. Depois do `il1`, rode os dois comandos abaixo, um de cada vez. No build do tutorial, os três runs usam a mesma regra do jogo.

No Windows:

```bash
mlagents-learn python/configs/imitation/FlappyBird_run2.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=il2 --initialize-from=il1 --no-graphics
mlagents-learn python/configs/imitation/FlappyBird_run3.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=il3 --initialize-from=il2 --no-graphics
```

No macOS:

```bash
mlagents-learn python/configs/imitation/FlappyBird_run2.yaml --env=builds/FlappyBird.app --run-id=il2 --initialize-from=il1 --no-graphics
mlagents-learn python/configs/imitation/FlappyBird_run3.yaml --env=builds/FlappyBird.app --run-id=il3 --initialize-from=il2 --no-graphics
```

## Lendo as curvas

Em um segundo terminal, com o ambiente virtual ativo, na raiz do repositório, rode o comando abaixo e abra http://localhost:6006 no navegador:

```bash
tensorboard --logdir results
```

Além das tags de PPO já vistas no Módulo 1 (Cumulative Reward, Episode Length, Policy Loss, Entropy), acompanhe três novas:

- `Losses/Pretraining Loss`: o quanto a política ainda difere da demonstração via BC. Tende a cair ao longo do treino, conforme o agente se aproxima do que foi demonstrado.
- `Losses/GAIL Loss`: a perda do discriminador do GAIL, que tenta distinguir a política do agente da demonstração. Como em qualquer treino adversarial, é normal essa curva oscilar em vez de cair de forma limpa. Uma queda rápida demais para perto de zero pode ser sinal do discriminador vencendo fácil demais, o que deixa o sinal de GAIL menos útil.
- `Policy/Gail Reward`: a recompensa extra que o GAIL soma à recompensa total, com base em quão perto da demonstração o discriminador julga a política atual.

Compare a curva do seu `il1` com a do `ppo1`, o mesmo orçamento de 50 mil passos, se o `ppo1` já tiver terminado. Também dá para abrir as três referências do TCC, em `results/reference/FlappyBird_il_run1`, `_run2` e `_run3`, para ler as curvas de BC e GAIL.

Atenção: as referências do TCC foram treinadas em versões diferentes do jogo. No run1 e no run2, bater não matava, e os episódios eram longos. A recompensa acumulada vai de cerca de -29 a +9.5 no run1. No run2, vai de -27 a +21.5. Só o run3 usa a regra letal do build do tutorial. Cada run partiu do anterior com `--initialize-from`, então compare a forma das curvas, não os valores absolutos.

Com `extrinsic.strength` baixo e `behavioral_cloning`/`gail` altos, como no run1, a hipótese é que a recompensa acumulada suba mais rápido logo no início, puxada pela demonstração. No run3, com os pesos praticamente invertidos, o reforço domina. Como o run3 partiu do modelo do run2, a curva dele já começa positiva e não se compara com a do `ppo1`.

## Para saber mais

- [docs/01-primeiro-agente.md](01-primeiro-agente.md), para o ciclo de vida do `Agent` e o gancho de reward hacking.
- [docs/03-projeto-final.md](03-projeto-final.md), para o desafio de design sobre o FlappyBird, com BC e GAIL como opções de menu.
- [docs/04-guia-de-referencia.md](04-guia-de-referencia.md), para lições, gargalos e a referência ao TCC do autor.
- Repositório oficial do Unity ML-Agents: https://github.com/Unity-Technologies/ml-agents
- Manual do pacote `com.unity.ml-agents` 4.1: https://docs.unity3d.com/Packages/com.unity.ml-agents@4.1/manual/index.html
