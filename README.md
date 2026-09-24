# Aplicação Prática de Aprendizado por Reforço e Imitation Learning com Unity ML-Agents

Repositório do tutorial do **SBGames 2026** (Goiânia/GO, 29/09 a 02/10/2026), o artefato permanente e citável associado ao trabalho.

*Practical Application of Reinforcement Learning and Imitation Learning with Unity ML-Agents: tutorial artifact for SBGames 2026. All content is in Brazilian Portuguese.*

> [!NOTE]
> **Repositório em finalização.** O material está sendo revisado e completado até 28/09/2026, véspera do tutorial.

## Sobre o tutorial

O tutorial propõe uma abordagem pedagógica estruturada para a transição entre os conceitos teóricos e a implementação prática do Aprendizado por Reforço (*Reinforcement Learning*, RL) e do Aprendizado por Imitação (*Imitation Learning*, IL) no desenvolvimento de jogos, usando o *toolkit* [Unity ML-Agents](https://github.com/Unity-Technologies/ml-agents). São cinco módulos *hands-on*, 3 horas líquidas na terça-feira 29/09/2026, das 9h00 às 12h30, com intervalo de 10h30 a 11h00, conduzidos por um ciclo iterativo de **problema → ferramenta → solução**, dos fundamentos do RL a um desafio de design sobre o agente do próprio tutorial, passando por técnicas de IL como Clonagem Comportamental (*Behavioral Cloning*, BC) e *Generative Adversarial Imitation Learning* (GAIL).

## Dois caminhos

- **Caminho B (padrão).** Só Python, mais o jogo FlappyBird já compilado, para Windows ou macOS. Sem Unity Editor. É o caminho usado no laboratório do evento.
- **Caminho A (opcional).** Unity Editor além do Python, para quem já tem uma conta Unity ID própria. As máquinas do laboratório não têm contas Unity, então o Caminho A depende de trazer a sua.

Os dois caminhos seguem a mesma agenda. Muda só a coluna do participante em cada módulo, detalhada em `docs/01-primeiro-agente.md` a `docs/03-projeto-final.md`.

## Agenda (29/09/2026, 9h00 a 12h30)

| Módulo | Horário | Duração | Atividade | Material |
|---|---|---|---|---|
| 0. Introdução | 9h00 a 9h30 | 30 min | Abertura e nivelamento conceitual: agente, ambiente, observação, ação, recompensa, episódio, política, ciclo ML-Agents, TensorBoard | Slides |
| 1. Primeiro agente | 9h30 a 10h30 | 60 min | Basic ("Hello World") em demonstração (20 min) e FlappyBird com PPO em laboratório (40 min) | `python/configs/ppo/Basic_ppo.yaml`, `python/configs/ppo/FlappyBird_ppo.yaml` |
| 2. Imitação | 11h00 a 11h20 | 20 min | Demonstração de gravação e leitura das curvas de BC e GAIL do TCC; treino ao vivo só se o teste do arquivo `.demo` tiver passado | `python/configs/imitation/`, `Demos/` |
| 3. Projeto final | 11h20 a 12h10 | 50 min | Desafio de design sobre o FlappyBird: uma mudança por vez, uma previsão, treino e comparação com a linha de base | `python/configs/desafio/FlappyBird_desafio.yaml` |
| 4. Encerramento | 12h10 a 12h30 | 20 min | Síntese, nota sobre uso de IA, próximos passos e perguntas | Slides |

Intervalo de 10h30 a 11h00, entre os módulos 1 e 2. A numeração e a ordem dos módulos seguem o artigo do tutorial, que prometeu 240 min; o slot do evento dá 180 min líquidos, e esta é a agenda recortada para o dia.

## Antes do dia

1. Clone este repositório, ou baixe o ZIP pelo GitHub.
2. Siga `docs/00-instalacao.md` para instalar Python, PyTorch, o mlagents e, no Caminho A, o Unity Editor.
3. Com o ambiente virtual ativado, rode `python scripts/verify_env.py`, como descrito na seção 4 de `docs/00-instalacao.md`, e confira que não há nenhuma FALHA no resultado.
4. Baixe o build do FlappyBird na [Release v0.9.0](https://github.com/lucasbrandao4770/sbgames2026-tutorial-mlagents/releases/tag/v0.9.0) (pré-lançamento): `FlappyBird-Windows-x64.zip` no Windows ou `FlappyBird-macOS.zip` no macOS. Descompacte o conteúdo em uma pasta `builds/` na raiz do repositório clonado, de forma que o executável fique em `builds/FlappyBird-Windows-x64/FlappyBird.exe` ou em `builds/FlappyBird.app`.

Quem for usar uma máquina do laboratório do evento não precisa destes passos: o pacote já estará instalado, e o mesmo build estará também no servidor interno do laboratório.

## Como treinar

Rode os comandos abaixo a partir da raiz do repositório clonado: os yamls de imitação referenciam `Demos/` como caminho relativo ao diretório de trabalho, e rodar de outra pasta faz o carregamento da demonstração falhar.

Troque `<build>` por `builds/FlappyBird-Windows-x64/FlappyBird.exe` no Windows ou por `builds/FlappyBird.app` no macOS.

Módulo 1, FlappyBird com PPO, com gráficos ligados:

```bash
mlagents-learn python/configs/ppo/FlappyBird_ppo.yaml --env=<build> --run-id=ppo1
```

Módulo 2, variante de imitação, só se o teste do arquivo `.demo` tiver passado, confirmado no dia:

```bash
mlagents-learn python/configs/imitation/FlappyBird_run1.yaml --env=<build> --run-id=il1 --no-graphics
```

Módulo 3, desafio de design, sempre comparado com o run `ppo1`:

```bash
mlagents-learn python/configs/desafio/FlappyBird_desafio.yaml --env=<build> --run-id=ppo2 --no-graphics
```

Regras do dia:

- Para relançar um `--run-id` já usado, adicione `--force`; sem essa opção o mlagents-learn recusa sobrescrever o run.
- Às 10h05 o treino do Módulo 1 para com `Ctrl+C`, tenha ou não terminado os 50 mil passos: o ONNX é exportado mesmo assim, e as curvas são lidas como estão.
- Os resultados de cada run ficam em `results/<run-id>/`. Para comparar curvas, rode `tensorboard --logdir results` a partir da raiz do repositório.

## Estrutura do repositório

```
.
├── README.md
├── requirements.txt              pilha Python para Windows e Linux x86_64
├── docs/                         guias de instalação e dos módulos (00 a 04)
├── scripts/
│   └── verify_env.py             confere a pilha Python antes do tutorial
├── python/configs/
│   ├── ppo/                      Basic e FlappyBird com PPO
│   ├── imitation/                três runs de BC e GAIL do TCC (run1, run2, run3)
│   └── desafio/                  template do desafio de design do Módulo 3
├── Demos/                        as duas demonstrações usadas pelos yamls de imitação
├── results/reference/            curvas de referência do TCC e do spike, para comparar no TensorBoard
├── unity/SBGamesMLAgents/        projeto Unity completo (Caminho A)
├── LICENSE                       MIT, para código
└── LICENSE-docs                  CC BY 4.0, para textos e materiais didáticos
```

## Documentação

- [`docs/00-instalacao.md`](docs/00-instalacao.md): instalação de Python, PyTorch, mlagents e, no Caminho A, do Unity Editor, para Windows e macOS.
- [`docs/01-primeiro-agente.md`](docs/01-primeiro-agente.md): o agente Basic ("Hello World"), o laboratório de FlappyBird com PPO e o currículo por níveis (Level1 a Level3), para reproduzir com calma.
- [`docs/02-imitacao.md`](docs/02-imitacao.md): gravação de demonstrações com o Demonstration Recorder e o receituário completo de BC e GAIL.
- [`docs/03-projeto-final.md`](docs/03-projeto-final.md): o desafio de design do Módulo 3 e o roteiro para projetar um ambiente próprio do zero.
- [`docs/04-guia-de-referencia.md`](docs/04-guia-de-referencia.md): lições, soluções e gargalos práticos registrados ao longo do tutorial.

## Resultados de referência

`results/reference/` guarda as curvas de treinamento do TCC (2024) e do spike de 24/09/2026: um run de PPO contra o build do FlappyBird e os três runs de imitação (BC e GAIL) usados no Módulo 2. Nenhum deles tem os checkpoints `.pt`, só os eventos do TensorBoard, o ONNX final e a configuração usada. Para abrir ao lado dos seus próprios runs, rode `tensorboard --logdir results` a partir da raiz do repositório. Detalhes de cada run estão em `results/reference/README.md`.

## Nota sobre uso de IA

Os autores usaram um assistente de IA (Claude, da Anthropic) para redigir e revisar documentação, comentários de configuração e scripts deste repositório, sempre sob supervisão dos autores. Todos os fatos técnicos foram conferidos contra o TCC dos autores (2024) e pela execução do código. Os autores são responsáveis pelo conteúdo final.

## Como citar

```
RODRIGUES, Lucas Brandão; ALMEIDA, Maria Carolina X. de; MOREIRA, Anna Pietra V. L. B. Aplicação Prática de Aprendizado por Reforço e Imitation Learning com Unity ML-Agents. Tutorial, SBGames 2026, Goiânia, 2026.
```

## Licença

O código deste repositório (scripts C#, scripts Python, configurações de treinamento e o projeto Unity) está sob a licença MIT, no arquivo `LICENSE`. Os textos, a documentação e os materiais didáticos (`README.md`, `docs/` e slides) estão sob a licença Creative Commons Atribuição 4.0 Internacional, no arquivo `LICENSE-docs`.

Exceções: os assets de exemplo da Unity em `unity/SBGamesMLAgents/Assets/SharedAssets/` seguem a licença Apache 2.0 da Unity Technologies, e os sprites e sons do Flappy Bird em `Assets/FlappyBird/Sprites/` e `Assets/FlappyBird/Sounds/` pertencem aos seus autores originais e são usados apenas para fins educacionais. Os detalhes estão em `THIRD_PARTY_NOTICES.md`.

## Autores

Instituto de Informática, Universidade Federal de Goiás (UFG)

- [Lucas Brandão Rodrigues](https://github.com/lucasbrandao4770)
- [Maria Carolina X. de Almeida](https://github.com/mariacxda)
- [Anna Pietra V. L. B. Moreira](https://github.com/pietra-leon)
