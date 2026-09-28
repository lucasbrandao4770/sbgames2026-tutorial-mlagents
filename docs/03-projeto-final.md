# Módulo 3: Projeto final (desafio de design)

## Objetivo

Este módulo acontece das 11h20 às 12h10 (50 min), logo depois do Módulo 2 e antes do encerramento.

A proposta original do tutorial previa projetar um ambiente novo do zero. Aqui o desafio é limitado. Cada participante escolhe uma decisão de design sobre o FlappyBird já treinado no Módulo 1. Depois escreve uma previsão de uma frase, treina um segundo run e compara o resultado com a linha de base da sala.

A ideia não é encontrar a melhor configuração possível em 25 minutos de treino. É praticar o ciclo completo de uma decisão de design em RL: prever, treinar, observar a curva, explicar o que aconteceu.

## Pré-requisitos

- [docs/01-primeiro-agente.md](01-primeiro-agente.md) concluído, com o FlappyBird treinado por PPO no Módulo 1 (o run `ppo1`).
- Um run `ppo1` salvo em `results/`, visível no TensorBoard.
- Opcional: [docs/02-imitacao.md](02-imitacao.md), se você quiser usar `behavioral_cloning` ou `reward_signals.gail` no menu abaixo.

## Parte 1: o desafio de design do dia

A regra é simples: uma mudança por vez.

Antes de treinar, escreva em uma frase o que você espera que aconteça com a curva de recompensa. Depois treine com um novo `--run-id` e compare sempre com o `ppo1` da Parte 2 do Módulo 1.

Horário: das 11h20 às 11h25, escolha a mudança e escreva a previsão (forme dupla se faltar máquina). Das 11h25 às 11h50, treine com `--no-graphics`. Na máquina de referência, um run de 50 mil passos levou de 75 a 115 segundos. No laboratório, a estimativa é de 2 a 4 vezes esse tempo. Quem terminar antes escolhe outra mudança e roda de novo com um novo `--run-id`, como `ppo3`.

### Menu de mudanças

Os valores de "Padrão" abaixo são os do `python/configs/ppo/FlappyBird_ppo.yaml`, o mesmo arquivo usado no Módulo 1.

| Parâmetro | Padrão | O que tentar | Efeito esperado |
|---|---|---|---|
| `learning_rate` | 3.0e-4 | 1.0e-4 ou 1.0e-3 | menor tende a deixar o treino mais lento e mais estável; maior aprende mais rápido no início, mas fica mais instável |
| `beta` | 5.0e-4 | 1.0e-2 | beta mais alto aumenta o peso da entropia e mantém o agente mais aleatório por mais tempo, o que ajuda se a política travar sempre no mesmo comportamento; a faixa recomendada pela documentação oficial é 1e-4 a 1e-2 |
| `reward_signals.extrinsic.gamma` | 0.99 | 0.9 ou 0.999 | menor faz o agente valorizar menos recompensas futuras, ficando mais imediatista; maior dá mais peso ao que vem depois do próximo cano |
| `time_horizon` | 200 | 64 ou 500 | menor corta a trajetória mais cedo e completa o resto com a estimativa de valor da rede, com mais viés e menos variância; maior usa mais recompensas reais antes de cortar, com menos viés e mais variância. A frequência das atualizações não muda: ela depende do `buffer_size` |
| `hidden_units` | 128 | 64 ou 256 | rede menor treina mais rápido, mas com menos capacidade; rede maior pode aprender padrões mais complexos, exigindo mais que 50 mil passos para compensar |
| `num_layers` | 2 | 1 ou 3 | menos camadas deixam a rede mais simples e rápida; mais camadas aumentam a capacidade, com o mesmo risco de não convergir a tempo |
| `batch_size` | 256 | 64 ou 512 | menor faz mais passos de gradiente por atualização, cada um mais ruidoso; maior suaviza o gradiente, mas faz menos passos em 50 mil passos de treino |
| `buffer_size` | 1024 | 2048 ou 4096 | buffer maior junta mais experiência antes de cada atualização, o que estabiliza cada atualização, mas faz menos atualizações em 50 mil passos. A documentação oficial recomenda de 2048 a 409600 para PPO, acima do valor atual |
| `max_steps` | 50000 | 100000 | como `learning_rate_schedule` é linear, dobrar `max_steps` faz a taxa de aprendizado, o `beta` e o `epsilon` decaírem mais devagar; é esse o efeito que aparece se o `Ctrl+C` interromper o treino antes do fim |
| `reward_signals.curiosity` | ausente (bloco não existe no config) | descomentar o bloco no `FlappyBird_desafio.yaml`, com `strength: 0.02`, `gamma: 0.99` e `learning_rate: 3.0e-4` (faixa típica de `strength`: 0.001 a 0.1) | recompensa intrínseca por estados que o agente ainda prevê mal, útil quando a recompensa do jogo é esparsa, como o `+1` que só vem ao passar um cano |
| `behavioral_cloning` (só se os instrutores anunciarem a variante de imitação) | ausente | descomentar o bloco, com `demo_path: Demos/Level1FlappyAgentDemo.demo` e `strength: 1.0` (valores do run1) | puxa a política para perto da demonstração gravada, tende a acelerar o começo do treino |
| `reward_signals.gail` (só se os instrutores anunciarem a variante de imitação) | ausente | descomentar o bloco, com `demo_path: Demos/Level1FlappyAgentDemo.demo` e `strength: 0.5` (valores do run1) | recompensa por se parecer com a demonstração, efeito parecido ao `behavioral_cloning`, mas aprendido por um discriminador |

Para ligar qualquer um dos três blocos comentados acima (`curiosity`, `behavioral_cloning` ou `gail`), apague os dois caracteres `# ` (cerquilha e espaço) do início de cada linha do bloco. Apagar só a cerquilha deixa um espaço a mais, e o `mlagents-learn` recusa o arquivo.

### Fluxo de trabalho

Abra `python/configs/desafio/FlappyBird_desafio.yaml` e edite o próprio arquivo. Ele traz os mesmos valores do `FlappyBird_ppo.yaml`, com as opções do menu comentadas, prontas para descomentar.

Edite o parâmetro escolhido e escreva sua previsão de uma frase antes de treinar.

No Windows:

```bash
mlagents-learn python/configs/desafio/FlappyBird_desafio.yaml --env=builds/FlappyBird-Windows-x64/FlappyBird.exe --run-id=ppo2 --no-graphics
```

No macOS:

```bash
mlagents-learn python/configs/desafio/FlappyBird_desafio.yaml --env=builds/FlappyBird.app --run-id=ppo2 --no-graphics
```

Rode sempre da raiz do repositório.

Compare `ppo2` com `ppo1` no TensorBoard. Em um segundo terminal, com o ambiente virtual ativo, na raiz do repositório:

```bash
tensorboard --logdir results
```

Depois abra http://localhost:6006 no navegador.

### Caminho A: mudanças em código

Quem tem Unity ID pode ir além do menu de configuração e editar `FlappyAgent.cs` diretamente, em `unity/SBGamesMLAgents/Assets/FlappyBird/Scripts/MLAgents/`. Abra primeiro a cena `Assets/FlappyBird/Scenes/mainGame.unity`.

Exemplo de mudança na recompensa: em `HandleFlappyCollision()`, a penalidade de colisão é `AddReward(-1.0f)`. Trocar por um valor menor testa se o agente passa a se arriscar mais perto dos canos.

```csharp
else if (e.Tag == "Pipe" || e.Tag == "Wall")
{
    AddReward(-0.3f); // original: AddReward(-1.0f)
}
```

Exemplo de mudança na observação: em `CollectObservations()`, adicione uma chamada a `sensor.AddObservation()` com a altura do centro do próximo vão de cano. Siga o mesmo estilo da observação de distância que já existe (`GetDistanceToNextPipe()`).

```csharp
float heightOfNextGapCenter = GetNextGapCenterHeight(); // método novo, a escrever
sensor.AddObservation(heightOfNextGapCenter / 10f); // mesma normalização da altura
```

Mudar o número de observações também exige aumentar o Space Size em Behavior Parameters, de 4 para 5 neste exemplo. E exige treinar de novo do zero: um modelo já treinado não reaproveita pesos de uma rede com outro Space Size.

Depois de editar e salvar o script, treine no editor, sempre a partir da raiz do repositório:

```bash
mlagents-learn python/configs/desafio/FlappyBird_desafio.yaml --run-id=ppo2_editor
```

Sem `--env`, o comando espera a conexão do Editor. Quando aparecer "Listening on port 5004. Start training by pressing the Play button in the Unity Editor.", aperte Play na cena `mainGame.unity`. Num teste curto no editor da máquina de referência, o treino do FlappyBird rodou a cerca de 90 passos por segundo. Nesse ritmo, 50 mil passos levam cerca de 10 min. Lance até as 11h35 ou reduza `max_steps` para caber no tempo. Ao final, ou a qualquer momento com `Ctrl+C`, o treinador exporta `results/ppo2_editor/FlappyAgent.onnx`.

Pare o Play, copie esse arquivo para `unity/SBGamesMLAgents/Assets/FlappyBird/TFModels/` e arraste o arquivo copiado para o campo Model do Behavior Parameters do Flappy. Mude Behavior Type para Inference Only e aperte Play de novo para ver o resultado. Um segundo run no editor exige um novo `--run-id` ou a flag `--force`.

## Parte 2: analisando resultados

Cada run deste módulo usa uma única seed. Isso significa que uma mudança isolada pode ficar dentro da variação natural do treino, sem ligação nenhuma com o parâmetro alterado.

Por isso, antes de julgar qualquer mudança, use os runs `ppo1` da própria sala como linha de base do ruído. Nos testes da preparação, três runs idênticos terminaram entre +2,3 e +6,6. Todas as máquinas rodaram a mesma configuração no Módulo 1. A diferença entre essas curvas mostra o quanto duas execuções idênticas já variam por conta da seed, sem nenhuma mudança de design.

No TensorBoard, compare pelo menos estas curvas entre `ppo2` e `ppo1`: Cumulative Reward, Episode Length, Policy Loss e Entropy. Se a diferença entre `ppo2` e `ppo1` for do tamanho da variação que já existe entre os `ppo1` da sala, o resultado é inconclusivo. Se for bem maior, há indício de um efeito real.

Alguns efeitos comuns, com o raciocínio por trás:

- `learning_rate` mais alto costuma acelerar o início do treino, mas a curva de Policy Loss tende a ficar mais irregular.
- `beta` mais alto mantém a Entropy alta por mais tempo: o agente demora mais para se fixar em uma política. Se a entropia cair rápido demais no `ppo1`, a documentação oficial sugere aumentar o `beta`.
- `reward_signals.extrinsic.gamma` mais baixo tende a produzir um agente que reage bem ao cano mais próximo, mas planeja pior a sequência de canos seguintes.
- `reward_signals.curiosity` tende a ajudar mais no começo do treino, quando o agente ainda não passou por nenhum cano e só conhece o -1 da colisão.
- `max_steps` menor corta o treino antes, então é comum ver a curva de Cumulative Reward ainda subindo quando o treino para, sem ter estabilizado.
- `behavioral_cloning` ou `reward_signals.gail`, quando ativos, tendem a puxar a recompensa para cima logo no início, por causa da demonstração. Com só 50 mil passos, isso não garante um resultado final melhor que o do `ppo1`.

Ao final, de 4 a 6 participantes mostram sua comparação para o grupo. Ligue o que aconteceu à observação, à ação, à recompensa, ao sinal intrínseco versus extrínseco e ao comportamento emergente do agente. Compare também com o que as curvas do TCC mostram para casos parecidos.

O módulo fecha com uma demonstração de 3 min no editor dos três modelos de currículo do projeto (Level1, Level2 e Level3, em `Assets/FlappyBird/TFModels/`), treinados em dificuldade crescente. Veja a Parte 3 e [docs/04-guia-de-referencia.md](04-guia-de-referencia.md) para o que ficou de fora dessa prática.

## Parte 3: seu próprio ambiente (autoestudo)

A proposta original deste módulo pedia que cada participante projetasse, implementasse e treinasse um agente autônomo em um ambiente novo, dentro de um jogo ou simulação complexa. Com o tutorial reduzido a três horas, esse projeto aberto virou material de autoestudo.

### Como pensar o design de um ambiente

Um ambiente de treinamento no ML-Agents precisa de três coisas. A primeira é um início automático de cena: a simulação começa sozinha quando o processo de treino é lançado. A segunda é um reset de episódio bem definido, normalmente feito pela Academy no início de cada episódio. A terceira é um fim de episódio claro, por `Max Steps` ou por uma chamada explícita a `EndEpisode()`.

### Checklist: observação, ação, recompensa, episódio

**Observação.** Reúna a informação que um humano precisaria para resolver o problema olhando a tela. Mantenha o tamanho e a ordem das observações sempre iguais a cada chamada. Ajuste o Space Size em Behavior Parameters para bater com o número de valores enviados ao `VectorSensor`. Normalize os valores para uma faixa parecida entre si, como o FlappyAgent já faz ao dividir altura, velocidade e distância por seus valores máximos esperados antes de cada `AddObservation()`. Para dados categóricos, use codificação one-hot em vez de um único número.

**Ação.** Prefira poucas ações: quanto menor o espaço de ação, mais fácil o aprendizado. Ações contínuas devem ficar dentro de uma faixa definida, normalmente `-1` a `1`.

**Recompensa.** Comece simples e adicione complexidade aos poucos. A recompensa deve refletir o resultado que você quer, não uma ação específica que parece levar até lá. Mantenha a magnitude de cada recompensa dentro de `-1` a `1` para um treino mais estável. Use `AddReward()` para somar valores entre uma decisão e outra e `SetReward()` para substituir o que foi somado desde a última decisão, não o total do episódio.

**Episódio.** Defina claramente quando ele começa (reset em `OnEpisodeBegin()`) e quando termina (`Max Steps`, `EndEpisode()`, ou os dois). A duração do episódio deve caber na complexidade da tarefa. Episódios muito longos atrasam o aprendizado. Episódios muito curtos podem não dar tempo de o agente completar a tarefa nem uma vez.

### Armadilhas comuns

- **Reward hacking.** Quando a recompensa premia uma ação específica em vez do resultado desejado, o agente tende a maximizar essa recompensa sem resolver a tarefa. A defesa é sempre voltar à pergunta: essa recompensa está descrevendo o resultado que eu quero, ou um comportamento que eu acho que leva até ele?
- **Recompensa esparsa.** Recompensas raras, que só aparecem ao atingir o objetivo final, tornam a exploração difícil. É o caso do exemplo clássico de grade do ML-Agents, com `+1` só ao alcançar o objetivo e `-1` só ao cair num buraco: o agente precisa explorar bastante antes de encontrar o primeiro sinal útil. O FlappyBird tem o mesmo problema em menor escala, já que o `+1` só vem ao passar um cano inteiro.
- **Observações sem normalizar.** Sem normalizar, cada observação chega à rede em uma escala diferente, o que atrapalha o treino. É por isso que o FlappyAgent divide altura, velocidades e distância por um valor máximo antes de cada `AddObservation()`, em vez de enviar os valores brutos.
- **Episódios que nunca terminam.** Sem `Max Steps` nem `EndEpisode()`, o episódio nunca fecha e o agente não recebe um sinal claro de que a tentativa acabou. No FlappyBird do tutorial, `EndEpisode()` está comentado de propósito, porque o jogo recarrega a cena quando o pássaro morre. O agente é destruído junto com a cena, e o ML-Agents fecha o episódio nesse momento. Se o pássaro sobreviver, o Max Step de 5000 passos do agente encerra o episódio. O `max_steps` do yaml encerra o treino, não o episódio.

### Um caminho sugerido

Basic (o "Hello World" do Módulo 1, um alvo simples e poucas observações) é o ponto de partida mais simples. FlappyBird (Ray Perception Sensor mais observações manuais, uma ação discreta, recompensa esparsa) já mostra um jogo real, com regras próprias, controlado por cima pelo agente. O próximo passo natural é escolher um jogo simples já pronto, ou uma cena nova, e aplicar o checklist acima. Comece testando o design à mão, pelo `Heuristic()`, antes de treinar. Assim você confirma que a mecânica funciona antes de colocar o aprendizado por reforço em cima dela.

## Para saber mais

- [docs/00-instalacao.md](00-instalacao.md): guia de instalação do Python, do PyTorch e do Unity.
- [docs/01-primeiro-agente.md](01-primeiro-agente.md): Basic e o primeiro treino do FlappyBird com PPO.
- [docs/02-imitacao.md](02-imitacao.md): gravação de demonstrações, BC e GAIL completos.
- [docs/04-guia-de-referencia.md](04-guia-de-referencia.md): lições, gargalos, o que ficou de fora do tutorial ao vivo e a referência ao TCC do autor. O Apêndice 4 do TCC detalha o design de ambientes, observações, ações, recompensas e episódios usado como base desta parte.
