# Módulo 1: Primeiro agente

## Objetivo

Treinar dois agentes com Reinforcement Learning (RL) usando PPO. O Basic é demonstração do instrutor. O FlappyBird é a parte prática, com as mãos na massa. Ao final deste módulo, você entende o ciclo de vida de um `Agent` no Unity ML-Agents: observações, ações, recompensas e episódios. Você também sabe ler um arquivo de configuração de treino, chave por chave. E treinou um agente do zero contra o build do FlappyBird.

## Pré-requisitos

- Ambiente instalado conforme [docs/00-instalacao.md](00-instalacao.md), com `mlagents-learn --help` funcionando num ambiente virtual ativo (Python 3.10, PyTorch 2.2.1 CPU, mlagents 1.1.0).
- Repositório clonado ou baixado, com o terminal aberto na raiz dele. Todos os comandos deste módulo rodam da raiz do repositório.
- No Caminho B, o build do FlappyBird da [Release v0.9.2](https://github.com/lucasbrandao4770/sbgames2026-tutorial-mlagents/releases/tag/v0.9.2), descompactado na pasta `builds/` da raiz do repositório. O passo 4 de "Antes do dia", no [README.md](../README.md), mostra como. O executável fica em `builds/FlappyBird-Windows-x64/FlappyBird.exe` no Windows ou em `builds/FlappyBird.app` no macOS.
- No Caminho A, o projeto Unity `unity/SBGamesMLAgents` aberto no Editor 6000.3.22f1 (no laboratório, a 6000.3.24f1).

## Parte 1: Basic, o Hello World

Basic é o primeiro ambiente do tutorial. Um cubo azul, o agente, precisa aprender a andar até uma esfera verde, o alvo, numa plataforma. No projeto Unity, ele vive na cena `Assets/Basic/Scenes/Basic.unity`, no prefab `Basic - Lucas.prefab`. O script é `Assets/Basic/Scripts/MoveToGoalAgent.cs`, com Behavior Name `MoveToGoal_Improved`.

No dia do tutorial, o instrutor conduz esse treino como demonstração de 20 minutos, o "Hello World" do ML-Agents, antes do laboratório com o FlappyBird. Quem segue o Caminho A treina o Basic junto, no Editor. Quem segue o Caminho B pode reproduzir esta parte em casa, depois de instalar o Unity como em [docs/00-instalacao.md](00-instalacao.md).

### O ciclo de vida do Agent

Todo agente do ML-Agents é uma classe C# que herda de `Agent` e sobrescreve métodos que o ML-Agents chama em momentos específicos. `MoveToGoalAgent` não sobrescreve `Initialize()`. Ele não precisa configurar nada uma única vez: tudo que faz se repete a cada episódio, dentro de `OnEpisodeBegin()`.

```csharp
public override void OnEpisodeBegin()
{
    transform.localPosition = new Vector3(Random.Range(-5f, 5f), 0, Random.Range(0, 6f));
    targetTransform.localPosition = new Vector3(Random.Range(-4f, 4f), 0, Random.Range(1, 5f));
}
```

`OnEpisodeBegin()` roda no início de cada episódio. Isso inclui o primeiro episódio e todo episódio seguinte, depois de `EndEpisode()` ou ao atingir o MaxStep de 1000 passos. Ele reposiciona o agente e o alvo em pontos aleatórios da plataforma, para o agente não decorar uma trajetória fixa.

```csharp
public override void CollectObservations(VectorSensor sensor)
{
    sensor.AddObservation(transform.localPosition); // Agent position
    sensor.AddObservation(targetTransform.localPosition); // Target position
}
```

`CollectObservations()` roda a cada decisão e descreve o que o agente percebe do ambiente. Aqui são duas posições, a do próprio agente e a do alvo. Cada `Vector3` tem três valores, seis observações ao todo. É o mesmo número configurado em Space Size, no Behavior Parameters do prefab.

```csharp
public override void OnActionReceived(ActionBuffers actions)
{
    // Apply a small negative reward for each step
    AddReward(-1f / MaxStep); // Small penalty for each step

    float moveX = actions.ContinuousActions[0];
    float moveZ = actions.ContinuousActions[1];
    float movespeed = 3f;
    transform.localPosition += new Vector3(moveX, 0, moveZ) * Time.deltaTime * movespeed;
}
```

`OnActionReceived()` executa a ação escolhida: aqui, duas ações contínuas (mover em X e em Z), lidas de `actions.ContinuousActions`. O Decision Requester do prefab pede uma decisão a cada 5 passos e está com Take Actions Between Decisions ligado. Por isso `OnActionReceived()` roda a cada passo e repete a última ação entre uma decisão e outra. A primeira linha soma -1/`MaxStep` a cada passo. Com o `MaxStep` de 1000 do Inspector, um episódio que chega ao limite acumula -1. Isso incentiva o agente a chegar rápido, não só a chegar.

```csharp
public void OnTriggerEnter(Collider other)
{
    if (other.TryGetComponent<Goal>(out Goal goal))
    {
        SetReward(+1f); // Positive reward for reaching the goal
        floorMeshRenderer.material = winMaterial;
        EndEpisode();
    }
    if (other.TryGetComponent<Wall>(out Wall wall))
    {
        float distanceToGoal = Vector3.Distance(transform.localPosition, targetTransform.localPosition);
        float penalty = Mathf.Clamp(1f - (1f / (distanceToGoal + 1f)), 0.1f, 1f);
        SetReward(-penalty); // Apply scaled penalty
        floorMeshRenderer.material = loseMaterial;
        EndEpisode();
    }
}
```

`OnTriggerEnter()` não é um método do ciclo de vida do `Agent`. É o evento de trigger da física do Unity, usado aqui para decidir a recompensa. Tocar o alvo (`Goal`) dá recompensa fixa de +1. Tocar uma parede (`Wall`) dá uma penalidade que cresce com a distância até o alvo, entre 0.1 e 1.0. Assim, bater longe do alvo pesa mais que bater perto. Nos dois casos, `EndEpisode()` encerra o episódio, e o ML-Agents chama `OnEpisodeBegin()` de novo.

Este script também não sobrescreve `Heuristic()`. Não há controle manual por teclado configurado para o Basic. O agente só age pela política treinada ou pelo treinador, durante o treino.

### `Basic_ppo.yaml`, chave por chave

| Chave | O que é |
|---|---|
| `MoveToGoal_Improved` | Nome do Behavior. Precisa ser idêntico ao configurado no Behavior Parameters do prefab no Unity. |
| `trainer_type: ppo` | Algoritmo de treino. PPO é o padrão do ML-Agents. |
| `batch_size: 32` | Quantas amostras entram em cada passo do gradiente, cada minilote do buffer. |
| `buffer_size: 256` | Quantas amostras são coletadas antes de cada atualização. |
| `learning_rate: 0.0003` | O quanto o modelo muda a cada atualização. |
| `beta: 0.005` | Incentivo à exploração de ações menos óbvias. |
| `epsilon: 0.2` | Limite de quanto a política pode mudar por atualização, o "P" de PPO. |
| `lambd: 0.95` | Parâmetro do cálculo de vantagem (GAE), equilibra viés e variância. |
| `num_epoch: 3` | Quantas vezes o buffer inteiro é percorrido a cada atualização. |
| `learning_rate_schedule: linear` | A taxa de aprendizado cai linearmente até perto de zero ao longo do treino. |
| `normalize: false` | Se as observações são normalizadas pela média e variância acumuladas, antes de entrar na rede. |
| `hidden_units: 20` | Neurônios por camada da rede. |
| `num_layers: 1` | Camadas escondidas da rede. |
| `vis_encode_type: simple` | Como observações visuais seriam codificadas. Aqui só há vetores. |
| `gamma: 0.9` | Fator de desconto da recompensa extrínseca: o quanto recompensa futura vale menos que recompensa imediata. |
| `strength: 1.0` | Peso da recompensa extrínseca na recompensa total usada para treinar. |
| `keep_checkpoints: 5` | Número máximo de checkpoints guardados. Os mais antigos são apagados. |
| `max_steps: 500000` | Total de passos de treino. Quando bate esse número, o treinador para sozinho e exporta o `.onnx` final. |
| `time_horizon: 3` | Passos considerados de uma vez no cálculo de vantagem, antes de "cortar" o trecho para fins de treino. |
| `summary_freq: 2000` | A cada quantos passos o treinador escreve um resumo, visível no console e no TensorBoard. |

### Treinando o Basic (Caminho A)

```bash
mlagents-learn python/configs/ppo/Basic_ppo.yaml --run-id=basic1
```

Depois de rodar o comando, o treinador mostra "Listening on port 5004. Start training by pressing the Play button in the Unity Editor." e espera até 60 segundos. Abra a cena `Assets/Basic/Scenes/Basic.unity` e aperte Play. Ao conectar, o treinador imprime os hiperparâmetros lidos do yaml. Depois disso, o console passa a mostrar os passos avançando e a recompensa média por episódio. Num único run numa máquina de referência (MacBook com Apple Silicon, 23/09/2026), 16 mil passos levaram 53 segundos no Editor. Nesse run, a recompensa média subiu de cerca de -1,05 para -0,39. O yaml pede 500 mil passos, cerca de meia hora nesse ritmo. Para a demonstração, interrompa com `Ctrl+C` depois de 1 ou 2 minutos: o treinador exporta o ONNX mesmo assim.

Ao final, o treinador exporta o modelo em `results/basic1/MoveToGoal_Improved.onnx`. O Unity só enxerga arquivos dentro de `Assets/`, então copie esse arquivo para `unity/SBGamesMLAgents/Assets/Basic/TFModels/`. Depois arraste o arquivo copiado para o campo Model do Behavior Parameters do prefab. Mude Behavior Type para Inference Only. Aperte Play para ver o agente jogar sozinho. O prefab já vem com `MoveToGoal.onnx`, um modelo treinado antes, que serve para comparar com o seu.

## Parte 2: FlappyBird com PPO

O FlappyBird troca o cubo e a esfera por um jogo de verdade. O script `Assets/FlappyBird/Scripts/MLAgents/FlappyAgent.cs`, com Behavior Name `FlappyAgent`, controla o pássaro por cima do jogo original. Ele faz isso sem reescrever a lógica do jogo. O `FlappyScript.cs` só ganhou pequenos ajustes: um evento de colisão e métodos públicos para bater asas e ler altura e velocidade.

```csharp
public override void Initialize()
{
    flappy = GetComponent<FlappyScript>();

    // Subscribe to the collision event
    flappy.OnCollision += HandleFlappyCollision;
}

private void HandleFlappyCollision(object sender, FlappyScript.CollisionEventArgs e)
{
    if (e.Tag == "Pipeblank")
    {
        AddReward(1.0f); // Reward for passing a checkpoint
    }
    else if (e.Tag == "Pipe" || e.Tag == "Wall")
    {
        AddReward(-1.0f); // Penalty for hitting an obstacle
        //EndEpisode(); // The episode is ended when the scene is reset
    }
}
```

`Initialize()` roda uma vez por instância do agente, quando ele é ativado pela primeira vez. Como o FlappyBird recarrega a cena a cada morte, um agente novo nasce a cada vida. `Initialize()` roda de novo nesse momento. É ali que `FlappyAgent` busca a referência ao `FlappyScript` (o jogo original) e se inscreve no evento de colisão dele. A cada colisão, `HandleFlappyCollision()` decide a recompensa: +1 ao passar por um vão de canos (tag `Pipeblank`) e -1 ao bater num cano ou numa parede.

Repare que `EndEpisode()` está comentado. Isso é proposital. Quem recria o pássaro é o próprio jogo, que recarrega a cena ao morrer. O agente é destruído junto com a cena, e o ML-Agents fecha o episódio nesse momento. Se o pássaro sobreviver por 5000 passos, o Max Step do agente também encerra o episódio. Na inferência sem treinador, com o modelo rodando dentro do jogo, o ML-Agents não mostra pontuação nem recompensa. O painel de treino mostra as duas.

```csharp
public override void CollectObservations(VectorSensor sensor)
{
    // Add bird's normalized height
    float normalizedHeight = Mathf.Clamp(flappy.GetHeight() / 10f, 0f, 1f); // Assuming 10 is the max height
    sensor.AddObservation(normalizedHeight);

    // Add bird's normalized velocity
    Vector2 velocity = flappy.GetVelocity();
    sensor.AddObservation(velocity.x / 5f); // Assuming max X speed is 5
    sensor.AddObservation(velocity.y / 5f); // Assuming max Y speed is 5

    // Add distance to the next pipe (normalized)
    float distanceToPipe = GetDistanceToNextPipe();
    sensor.AddObservation(distanceToPipe / 10f); // Assuming 10 is the max distance to the next pipe
}
```

Essas quatro observações manuais (altura, velocidade em X, velocidade em Y e distância até o próximo cano, todas normalizadas) se somam às de uma Ray Perception Sensor 2D. Ela está configurada no objeto filho "Rays": 5 raios por direção, alcance 5, detectando as tags `Pipeblank`, `Pipe` e `Wall`. Esse sensor não aparece no script, porque é um componente à parte, adicionado direto no Inspector.

```csharp
public override void OnActionReceived(ActionBuffers actions)
{
    bool doJump = actions.DiscreteActions[0] == 1;

    if (doJump) {
        flappy.Jump();
    }
}

public override void Heuristic(in ActionBuffers actionsOut)
{
    ActionSegment<int> discreteActions = actionsOut.DiscreteActions;

    // Default action: no jump (0)
    discreteActions[0] = 0;

    // Check for manual input to trigger a jump (set to 1)
    if (Keyboard.current.spaceKey.IsPressed())
    {
        discreteActions[0] = 1;
    }
}
```

A ação é um único ramo discreto com dois valores: bater asas ou não. `OnActionReceived()` chama `flappy.Jump()` quando a ação decidida é 1. `Heuristic()` permite controlar o pássaro manualmente, sem modelo nem treinador, com a barra de espaço.

### `FlappyBird_ppo.yaml`, o que muda do Basic

| Chave | Valor | Diferença |
|---|---|---|
| `batch_size` / `buffer_size` | 256 / 1024 | Maiores que no Basic, para um problema um pouco mais complexo. |
| `beta` | 5.0e-4 | Bem menor que no Basic: menos incentivo a explorar ações aleatórias. |
| `lambd` | 0.99 | Acima do 0.95 do Basic. O cálculo de vantagem confia mais nas recompensas realmente recebidas e menos na estimativa de valor da rede. Menos viés, mais variância. |
| `hidden_units` / `num_layers` | 128 / 2 | Rede maior que os 20 neurônios e 1 camada do Basic. |
| `max_steps` | 50000 | Bem menor que os 500 mil do Basic: o treino do dia precisa caber em poucos minutos. |
| `time_horizon` | 200 | Mais passos considerados de uma vez, contra 3 no Basic. |
| `checkpoint_interval` | 10000 | A cada quantos passos um checkpoint intermediário é salvo em disco. |
| `extrinsic.strength` | 0.1 | Herdado do run1 de imitação do TCC. Ali, a recompensa do jogo pesava pouco para não competir com BC e GAIL. Sem imitação, é o único sinal de recompensa. O valor só muda a escala da recompensa usada no treino. |
| `extrinsic.gamma` | 0.99 | Recompensas futuras contam quase tanto quanto as imediatas. |

### Treinando o FlappyBird (o laboratório do dia)

No Windows:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=ppo1
```

No macOS:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird.app --run-id=ppo1
```

Como o comando já aponta para o build com `--env`, o jogo abre sozinho, com gráficos ligados, e o painel de treino aparece no canto superior esquerdo da janela.

#### O painel de treino

| Linha do painel | O que mostra |
|---|---|
| Treinador conectado / Inferência (sem treinador) | Treinador conectado: um `mlagents-learn` está conectado e decide as ações do agente, treinando ou, com `--inference`, só jogando. Inferência (sem treinador): nenhum `mlagents-learn` conectado; joga o `.onnx` da linha Modelo, ou você, se ela mostrar `nenhum (controle manual)` |
| Passos | Decisões tomadas pelo agente desta janela desde que o jogo abriu. Num treino novo, com um só ambiente, é o mesmo número que o treinador chama de Step |
| Episódios | Episódios terminados desde que o jogo abriu |
| Pontuação | Canos que o pássaro já passou na vida atual |
| Melhor pontuação | A maior pontuação de uma vida desde que o jogo abriu |
| Modelo | O `.onnx` que está jogando, ou `controlado pelo treinador` com o `mlagents-learn` conectado |
| Recompensa do episódio | Soma da recompensa do episódio em andamento |
| Média (últimos 20) | Média da recompensa final dos últimos 20 episódios |
| Últimos 50 episódios | Gráfico de barras com a recompensa final de cada um dos últimos 50 episódios |
| Velocidade | A barra e os botões 1x, 5x e 20x que controlam a velocidade do jogo |
| Som | Liga ou desliga o som do jogo. Com um `mlagents-learn` conectado, fica sempre desligado, mesmo sem treinar |
| Pasta | Com o treinador conectado, a pasta deste run dentro de `results`, como `results/ppo1`. Sem treinador, pode mostrar a execução mais recente de `results`, ou `nenhuma execução ainda`. No Editor, não aparece |
| Salvo | Há quanto tempo o treinador salvou o `.onnx` mais recente dessa pasta, e em qual passo, ou `modelo final`. Antes do primeiro `.onnx`, mostra `nada salvo ainda`. Aparece junto com Pasta |
| TensorBoard | Abre http://localhost:6006 no navegador. Antes, rode `tensorboard --logdir results` num segundo terminal, como no comando abaixo |
| A- e A+ | Diminuem ou aumentam o painel, como as teclas `-` e `=` ou as teclas `-` e `+` do teclado numérico |
| Rodapé | As teclas de atalho e a versão do jogo, como `v0.9.2` |

A janela abre com 1024x576 e pode ser redimensionada, tanto ao abrir o jogo com um clique duplo quanto quando o `mlagents-learn` o abre com gráficos. Durante o treino, não clique na área do jogo nem aperte a barra de espaço: o pássaro bate as asas fora do controle do treinador, e isso atrapalha o treino. Cliques no painel não mexem no pássaro. O som começa desligado. A chave do painel ou a tecla `M` liga o som, e essa escolha fica salva para as próximas vezes. Com um `mlagents-learn` conectado, o som fica sempre desligado, mesmo sem treinar. A tecla `H` esconde ou mostra o painel. As teclas `-` e `=` (a mesma do `+`), e também `-` e `+` do teclado numérico, diminuem ou aumentam o painel, até a altura da janela. Para um painel maior, aumente a janela. Num treino com horário de corte, como o do Módulo 1 no dia do tutorial, deixe a velocidade em 20x: em 1x o treino avança bem mais devagar, até cerca de 20 vezes. A Média (últimos 20) do painel e o Mean Reward que aparece no console fazem médias sobre janelas diferentes de episódios: os dois números não precisam bater.

Dá para acompanhar o pássaro treinando ao vivo, em velocidade acelerada. Enquanto treina, acompanhe o console: os passos avançando e a recompensa média subindo. Para o TensorBoard, abra um segundo terminal, ative o ambiente virtual, vá para a raiz do repositório e rode o comando abaixo. Depois abra http://localhost:6006 no navegador.

```bash
tensorboard --logdir results
```

As tags mais importantes no TensorBoard são quatro. Cumulative Reward é a recompensa acumulada por episódio: deve subir. Episode Length é a duração do episódio: deve crescer conforme o pássaro sobrevive mais. Policy Loss e Entropy também ajudam: a queda gradual da entropia indica que a política está ficando mais decidida. Compare sua curva com a referência em `results/reference/FlappyBird_ppo`. Ela é um de três runs de 50 mil passos feitos contra o build em 24/09, sem gráficos, e terminou em +5,3. Como a mesma configuração terminou entre +2,3 e +6,6 nesses três runs, uma curva abaixo da referência não indica erro.

A mesma configuração rodou várias vezes contra o build numa máquina de referência (MacBook), entre 24/09 e 28/09/2026. Sem tela (`--no-graphics`), runs de 50 mil passos levaram entre 60 e 115 segundos. Em três runs de 24/09, a recompensa média começou perto de -1,45 e terminou entre +2,3 e +6,6. Com gráficos ligados, como no comando acima, com a janela de 1024x576, runs de 50 mil passos levaram entre 2 e 3 minutos. Nas máquinas do laboratório, a estimativa, ainda não medida, é de 2 a 4 vezes mais lento. Uma saída para acelerar é `--num-envs=2`, só contra o build. Num run sem tela de 24/09, com dois ambientes, 50 mil passos levaram 52 segundos, cerca de 1,7 vez mais rápido que os 92 segundos de um ambiente só, no mesmo dia. Regra do dia: às 10h05 o treino para com `Ctrl+C`, treinado ou não. O `Ctrl+C` leva de 2 a 3 segundos para parar, e o treinador exporta o ONNX mesmo assim, com as curvas como estão. Para treinar de novo com o mesmo `--run-id`, é preciso acrescentar `--force`, senão o treinador recusa por já existir um run com esse nome.

## Reward hacking

"Reward hacking" acontece quando o agente maximiza exatamente o sinal de recompensa definido, não a intenção de quem desenhou essa recompensa. Se sobrar um atalho barato, um otimizador bom o suficiente encontra esse atalho.

O TCC registra um caso assim no ambiente PressButton. Ali, o agente precisa apertar um botão para liberar comida e depois buscá-la. Em alguns treinos, os agentes passaram a ficar "grudados" no botão sem apertá-lo. A correção mexeu na própria recompensa. O prêmio por apertar o botão subiu de +1 para +2. Ficar perto do botão sem apertar passou a custar -0.001 por passo. Se aproximar da comida passou a render +0.005 por passo. Assim sobrou menos espaço para o atalho.

A recompensa do FlappyBird é do mesmo tipo. É esparsa, com só dois valores, +1 e -1. O mesmo risco existe aqui. Durante o treino do dia, observe se a recompensa média trava perto de zero ou levemente negativa enquanto a duração do episódio cresce. Isso pode indicar que o agente achou um jeito de evitar o -1 sem buscar o +1.

## Currículo por níveis

O projeto traz três modelos treinados em `Assets/FlappyBird/TFModels/`: `FlappyAgentLevel1.onnx`, `FlappyAgentLevel2.onnx` e `FlappyAgentLevel3.onnx`. Eles são o resultado dos três runs de imitação do TCC descritos em [docs/02-imitacao.md](02-imitacao.md). Cada run treinou numa versão um pouco mais difícil do jogo. No run 1, os canos tinham posição e distância fixas, e bater não encerrava o episódio. No run 2, os canos ficaram aleatórios, ainda sem colisão letal. No run 3, os canos seguiram aleatórios e a colisão passou a matar, a mesma regra do jogo atual.

Treinar do mais fácil para o mais difícil, reaproveitando o checkpoint do run anterior a cada etapa (`--initialize-from`), é currículo por níveis (curriculum learning). O agente aprende o básico num cenário mais simples antes de encarar a versão completa. A cena `mainGame.unity` já vem com `FlappyAgentLevel3.onnx` atribuído no campo Model do Behavior Parameters do Flappy: é o modelo que joga quando alguém abre o jogo com um clique duplo, sem treinador, e aparece como `FlappyAgentLevel3` na linha Modelo do painel de treino. Para comparar os três, arraste cada `.onnx` para esse campo e aperte Play. Na versão atual do jogo, com uma regra só, a ideia é notar a diferença de comportamento entre uma política pouco treinada (Level1) e uma mais madura (Level3). Medidos no Editor em velocidade normal, o Level1 teve recompensa média de -0,86 em 50 vidas, com melhor pontuação 1, em cerca de 2 minutos. O Level3 teve +3,90 em 10 vidas, com melhor pontuação 13, em 3 minutos. No dia, essa comparação é só uma demonstração de 3 minutos conduzida pelo instrutor, não uma atividade prática.

## Assistir a um modelo treinado

Para ver o `ppo1` jogando sozinho, sem treinar e sem alterar a pasta do run treinado, rode este comando na raiz do repositório, com o ambiente virtual ativado, depois que o treino do Módulo 1 terminar. Se o seu run tiver outro nome, troque `ppo1` por ele.

No Windows:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=assistir --initialize-from=ppo1 --inference --force --time-scale=1 --capture-frame-rate=0 --max-lifetime-restarts=0
```

No macOS:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird.app --run-id=assistir --initialize-from=ppo1 --inference --force --time-scale=1 --capture-frame-rate=0 --max-lifetime-restarts=0
```

A forma do Windows não foi testada; ela só troca o caminho do `--env`. `assistir` é um nome de run descartável, recriado a cada execução do comando; `ppo1` é o run treinado, o mesmo nome usado no Módulo 1. `--time-scale=1` e `--capture-frame-rate=0` deixam o jogo perto do tempo real. Sem as duas opções, o jogo roda na velocidade de treino, bem mais rápido que o tempo real. Só com `--time-scale=1`, ele ainda roda quase 2 vezes mais rápido. `--max-lifetime-restarts=0` faz o comando terminar quando o jogo é fechado; sem essa opção, o treinador abre o jogo de novo. O jogo não treina: o console mostra `Not Training` em cada linha de resumo. Nesse modo, quem roda o modelo é o `mlagents-learn`, no Python. Por isso o painel mostra Treinador conectado, a linha Modelo mostra `controlado pelo treinador` e o som fica desligado. Em velocidade normal, a primeira linha de resumo leva cerca de 4 minutos para aparecer, porque o resumo sai a cada 2000 passos. Para parar, feche a janela do jogo ou aperte `Ctrl+C` no terminal. Depois de fechar a janela, o comando leva cerca de 15 segundos para terminar e mostra linhas `[ERROR]`, como `Worker 0 exceeded the allowed number of restarts.`: é o esperado. Atenção com `--force`: ele apaga o run com o nome dado em `--run-id`, por isso use sempre `assistir`, nunca `ppo1`. Sem `--force`, repetir o comando com o mesmo `--run-id=assistir` falha com "Previous data from this run ID was found. Either specify a new run ID, use --resume to resume this run, or use the --force parameter to overwrite existing data." Se o comando falhar logo depois de outro run com uma mensagem que cita `worker number 0 is still in use`, a porta ainda está ocupada: espere alguns segundos e rode de novo.

Existe uma forma mais curta, `--run-id=ppo1 --resume --inference`, mas ela roda dentro da própria pasta do run treinado: reescreve `configuration.yaml`, descarta os checkpoints originais e infla o contador de passos salvo, mesmo sem treinar nada. Por isso o comando recomendado é o de cima, com `--initialize-from` e um `--run-id` novo, que só lê o checkpoint do run treinado e grava tudo o que produz numa pasta separada.

## Problemas comuns

- **Porta ocupada.** Contra o build, o treinador usa a porta 5005 por padrão. No Editor, usa a 5004. Se outro treinador já estiver rodando na mesma máquina, feche esse treinador antes. Contra o build, outra saída é acrescentar `--base-port=5010` no comando. No Editor, `--base-port` não tem efeito, porque a porta é sempre 5004.
- **Treinador travado esperando o ambiente.** O treinador espera cerca de 60 segundos pela conexão. Confira se `--env` aponta para o executável certo. No Caminho A, confira também se o Play foi apertado no Editor.
- **O jogo abre e fecha, ou o treino não começa.** Leia o log do jogo. Quando o `mlagents-learn` abre o build, o log fica em `results/<run-id>/run_logs/Player-0.log`. Com o build aberto à mão, ele fica em `~/Library/Logs/INF-UFG/FlappyBird/Player.log` no macOS ou em `%USERPROFILE%\AppData\LocalLow\INF-UFG\FlappyBird\Player.log` no Windows.
- **Treinador lento para conectar em máquinas do laboratório.** Se 60 segundos não bastarem, use `--timeout-wait=120` para dar mais tempo à conexão.
- **Firewall do Windows.** Na primeira vez que o `mlagents-learn` abre o build, o Windows pode perguntar se libera o Python na rede. A conexão é só local, entre o treinador e o build na mesma máquina. Permita o acesso em redes privadas.
- **Caminho do build errado.** Confirme que o comando roda da raiz do repositório. Confirme também que o build foi descompactado em `builds/`, como no passo 4 de "Antes do dia" do [README.md](../README.md).
- **Windows bloqueia o `.exe` (SmartScreen) ou macOS bloqueia o `.app` (Gatekeeper).** No Windows, clique em "Mais informações" e depois em "Executar assim mesmo". No macOS, rode `xattr -dr com.apple.quarantine builds/FlappyBird.app` na raiz do repositório e repita o comando. Se ainda bloquear, no macOS 15 ou mais recente, abra `FlappyBird.app` uma vez com dois cliques e feche o aviso. Depois use "Abrir Mesmo Assim" em Ajustes do Sistema, Privacidade e Segurança.

## Para saber mais

- [docs/02-imitacao.md](02-imitacao.md), para Clonagem Comportamental e GAIL.
- [docs/03-projeto-final.md](03-projeto-final.md), para o desafio de design sobre o FlappyBird.
- [docs/04-guia-de-referencia.md](04-guia-de-referencia.md), para lições, gargalos e a referência ao TCC do autor.
- Repositório oficial do Unity ML-Agents: https://github.com/Unity-Technologies/ml-agents
- Manual do pacote `com.unity.ml-agents` 4.1: https://docs.unity3d.com/Packages/com.unity.ml-agents@4.1/manual/index.html
