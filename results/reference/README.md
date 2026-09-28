# Resultados de referência

Curvas de treinamento prontas, para comparar com os runs feitos ao vivo no tutorial. Cada pasta tem o modelo final em ONNX, o `configuration.yaml` usado e os arquivos JSON de `run_logs/`, sem os checkpoints `.pt`, que não entram no repositório. A maioria também tem o evento do TensorBoard. `FlappyBird_ppo_500k/` é a exceção às duas regras, explicada abaixo.

- `FlappyBird_ppo/`: PPO puro contra o build do FlappyBird, ensaio de 24/09/2026 em um MacBook com Apple Silicon, com `--no-graphics`, cerca de 2 min, 50 mil passos, configuração equivalente a `python/configs/ppo/FlappyBird_ppo.yaml`. Referência para comparar com os runs `ppo1` (Módulo 1) e `ppo2` (Módulo 3) do dia.
- `FlappyBird_ppo_500k/`: os mesmos hiperparâmetros de `FlappyBird_ppo/`, com `max_steps` de 500 mil em vez de 50 mil. Ensaio de 28/09/2026 no mesmo MacBook, com `--no-graphics`, em cerca de 12 minutos e meio, configuração equivalente a `python/configs/ppo/FlappyBird_ppo_500k.yaml`. A taxa de aprendizado cai em linha reta até o `max_steps`, então aqui ela cai 10 vezes mais devagar, e os dois runs não se comparam passo a passo. Aos 50 mil passos, este run já marcava +31,5, enquanto `FlappyBird_ppo/` terminou em +5,3. Um episódio do FlappyBird só termina na morte ou no limite de 5000 passos do agente, cerca de 1000 decisões, porque o agente decide a cada 5 passos. A partir de uns 80 mil passos, o pássaro quase não morre, e os episódios terminam nesse limite: por isso a recompensa média fica perto de +33. Jogando em velocidade normal por 3 minutos, o modelo final passou 62 canos sem morrer. É a referência de um run que chegou ao teto do jogo, não um resultado para reproduzir no dia.
- `FlappyBird_il_run1/`: etapa 1 de 3 do currículo de imitação do TCC (2024), treinada do zero no editor, numa versão do jogo com canos em posição fixa e colisões que não matam, por isso cada episódio dura cerca de 1000 passos. Recompensa extrínseca fraca e imitação forte (extrinsic 0.1, behavioral_cloning 1.0, gail 0.5), 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run1.yaml`. O `configuration.yaml` registra a demonstração como `Demos/FlappyAgentDemoLevel1.demo`; a demonstração do nível 1 deste repositório é `Level1FlappyAgentDemo.demo`.
- `FlappyBird_il_run2/`: etapa 2, iniciada do modelo final do run1 (`--initialize-from`), numa versão com canos em altura e distância aleatórias e colisões que ainda não matam. Recompensa extrínseca forte e imitação moderada (extrinsic 1.0, behavioral_cloning e gail 0.4) com `Leve2FlappyAgentDemo.demo`, mais 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run2.yaml`.
- `FlappyBird_il_run3/`: etapa 3, iniciada do modelo final do run2, com as regras do build do tutorial: colidir com cano ou parede reinicia o jogo. Recompensa extrínseca forte e imitação bem fraca (extrinsic 1.0, behavioral_cloning e gail 0.1) com `Leve2FlappyAgentDemo.demo`, mais 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run3.yaml`.

`FlappyBird_ppo_500k/` não traz o evento do TensorBoard, de propósito: assim `tensorboard --logdir results` continua comparando só runs de 50 mil passos. Em troca, é o único run desta pasta que guarda `FlappyAgent/checkpoint.pt`, para poder ser assistido jogando com o comando de inferência, a partir da raiz do repositório.

No Windows:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=assistir --initialize-from=reference/FlappyBird_ppo_500k --inference --force --time-scale=1 --capture-frame-rate=0 --max-lifetime-restarts=0
```

No macOS:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=builds/FlappyBird.app --run-id=assistir --initialize-from=reference/FlappyBird_ppo_500k --inference --force --time-scale=1 --capture-frame-rate=0 --max-lifetime-restarts=0
```

Para parar, feche a janela do jogo ou aperte `Ctrl+C` no terminal. Depois de fechar a janela, o comando leva cerca de 15 segundos para terminar e mostra linhas `[ERROR]`, como `Worker 0 exceeded the allowed number of restarts.`: é o esperado.

Para abrir ao lado dos seus próprios runs, rode `tensorboard --logdir results` a partir da raiz do repositório. O `FlappyBird_ppo` se compara direto com `ppo1` e `ppo2`, porque usa o mesmo build e a mesma configuração base. Os três runs de imitação servem para ler as curvas de BC e GAIL (Losses/Pretraining Loss, Losses/GAIL Loss, Policy/Gail Reward), não para comparar valores com o `il1`: o run1 e o run2 rodaram em versões do jogo sem morte, com episódios longos, e o run2 e o run3 partiram de modelos já treinados.

Os nomes de arquivo de evento e os caminhos dentro de `configuration.yaml` e `run_logs/` preservam a máquina onde cada run foi gravado (o Mac do Lucas para o PPO, um notebook Windows para os três runs de imitação do TCC), mantidos como registro de origem.
