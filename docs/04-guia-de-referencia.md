# Guia de referência

## Objetivo

Este é o guia de referência prometido pelo README: o registro sistematizado das lições, soluções e gargalos práticos observados na preparação e na realização do tutorial. Serve tanto para quem participou no dia 29/09/2026 quanto para quem chega ao repositório depois, sem ter passado pelo tutorial ao vivo.

Segundo o artigo do SBGames 2026, esse conhecimento raramente aparece de forma estruturada na literatura científica. Ele vem da experiência prática direta dos autores com os desafios reais de implementação. Este guia é a parte prática desse registro.

## Pré-requisitos

Nenhum: este guia pode ser lido antes, durante ou depois do tutorial.

## Síntese do tutorial

O tutorial segue um ciclo de problema, ferramenta e solução em cada um dos cinco módulos, com 180 minutos no total. Os Módulos 0 e 1 acontecem antes do intervalo, das 9h00 às 10h30. Os Módulos 2, 3 e 4 acontecem depois, das 11h00 às 12h30. O Caminho B, sem editor, é o padrão em todos os módulos. O Caminho A soma o treino do Basic no Módulo 1, a leitura de código no editor e, no Módulo 3, a edição direta de `FlappyAgent.cs`.

**Módulo 0, Introdução (30 min).** Problema: nivelar um grupo que chega com bagagens muito diferentes em RL e ML-Agents, sem tempo para configurar o ambiente ao vivo. Ferramenta: os conceitos de agente, ambiente, observação, ação, recompensa, episódio e política, mais o `verify_env.py` para confirmar que a máquina está pronta. Solução: todos os participantes começam as atividades práticas em condições equivalentes, com a configuração já feita antes do dia.

**Módulo 1, Primeiro agente (60 min).** Problema: um agente que aprende a alcançar um alvo, o "Hello World" do ML-Agents, seguido do primeiro treino de verdade, agora no FlappyBird. Ferramenta: espaços de observação e ação, função de recompensa, o algoritmo PPO e a leitura de curvas no TensorBoard. Solução: cada participante treina o FlappyBird com PPO contra o build e analisa as próprias curvas de treinamento, o primeiro ciclo completo de problema, ferramenta e solução do tutorial.

**Módulo 2, Imitação (20 min).** Problema: aprender uma tarefa a partir de demonstrações humanas, em vez de só tentativa e erro. Ferramenta: gravação de demonstrações, Behavioral Cloning e GAIL. Solução: leitura crítica comparando as curvas de BC e GAIL com as do PPO. Se os instrutores anunciarem a variante de imitação, cada participante faz também um treino curto ao vivo (`il1`).

**Módulo 3, Projeto final (50 min).** Problema: um desafio de design sobre o FlappyBird já treinado, com uma decisão, um treinamento e uma comparação. Ferramenta: integração de RL e IL, design de recompensas e hiperparâmetros, análise do comportamento emergente. Solução: cada participante testa uma hipótese, e o grupo compara os resultados contra a linha de base ruidosa da própria sala.

**Módulo 4, Encerramento (20 min).** Problema: fechar o tutorial de um jeito que o aprendizado continue depois do evento. Ferramenta: síntese das técnicas trabalhadas, sugestões de projetos futuros e algoritmos mais avançados. Solução: acesso ao repositório GitHub completo, com os projetos Unity, o código comentado e este guia de referência.

Ao final dos módulos práticos, o artigo prevê Momentos de Discussão estruturados, em que os participantes expõem dúvidas, compartilham dificuldades e trocam experiências. Por enquanto, as lições abaixo vêm da preparação do tutorial. Depois de 29/09/2026, este guia recebe também o que surgir nesses momentos.

## Lições e gargalos

Cada tabela abaixo lista um problema real encontrado na preparação do tutorial e a correção ou alavanca usada para contorná-lo.

### Instalação

Estas checagens acontecem antes do dia 29/09/2026, seguindo o [docs/00-instalacao.md](00-instalacao.md).

| Causa | Correção ou alavanca |
|---|---|
| O python.org não distribui instalador para a versão 3.10.12 | Usar o instalador da 3.10.11, a última da série 3.10 com instalador. O mlagents 1.1.0 aceita qualquer versão de 3.10.1 a 3.10.12 |
| O mlagents aceita qualquer PyTorch a partir da 2.1.1 | Fixar `torch==2.2.1` antes do mlagents, como faz o `requirements.txt` no Windows e no Linux. No macOS em Apple Silicon, siga a subseção 3.4 de [docs/00-instalacao.md](00-instalacao.md) |
| No macOS em Apple Silicon, o grpcio 1.48.2 ou anterior exigido pelo mlagents não tem pacote pronto para arm64 | Instalar grpcio 1.53.2 antes, depois o mlagents com `--no-deps`, com as demais dependências instaladas à parte |
| O setuptools 82 ou mais recente remove o módulo `pkg_resources`, ainda importado pelo mlagents e pelo tensorboard | Fixar `setuptools<80` num ambiente virtual novo |
| O Windows (SmartScreen) e o macOS (Gatekeeper) desconfiam do executável do FlappyBird baixado da aba Releases | No Windows, clique em "Mais informações" e depois em "Executar assim mesmo". No macOS, rode `xattr -dr com.apple.quarantine builds/FlappyBird.app` na raiz do repositório. Se ainda bloquear, no macOS 15 ou mais recente, abra o `FlappyBird.app` uma vez com dois cliques e feche o aviso. Depois use "Abrir Mesmo Assim" em Ajustes do Sistema, Privacidade e Segurança |
| Confirmar que o ambiente está pronto antes do dia do tutorial | `python scripts/verify_env.py`, que imprime OK, AVISO ou FALHA por checagem, com um resumo ao final |

### Treinamento

Estes pontos devem aparecer ao vivo, principalmente nos Módulos 1 e 3, os dois blocos de mão na massa do tutorial.

| Causa | Correção ou alavanca |
|---|---|
| Reexecutar um `--run-id` já usado falha | Acrescentar a flag `--force` |
| Dois treinos na mesma máquina disputam a mesma porta: 5005 contra o build, 5004 no Editor | Contra o build, `--base-port` escolhe outra porta para o segundo treino. No Editor, a porta é sempre 5004 |
| O treinador espera cerca de 60 s pela conexão antes de desistir | Com `--env`, o próprio `mlagents-learn` abre o build. Em máquinas lentas, `--timeout-wait=120` dá mais tempo. No Editor, aperte Play em até 60 s depois do comando |
| O jogo abre e fecha, ou o treino não começa, sem pista do motivo | Leia o log do jogo. Pelo treinador, em `results/<run-id>/run_logs/Player-0.log`. Aberto à mão, em `~/Library/Logs/INF-UFG/FlappyBird/Player.log` no macOS ou em `%USERPROFILE%\AppData\LocalLow\INF-UFG\FlappyBird\Player.log` no Windows |
| Treinar com a janela do jogo renderizada é mais lento | Usar `--no-graphics`. Numa máquina de referência (MacBook, 24/09/2026), três runs de 50 mil passos contra o build levaram de 75 a 115 s sem gráficos (cerca de 440 a 670 passos por segundo). Com gráficos, um run levou 156 s (cerca de 320 passos por segundo) |
| Um único ambiente limita a velocidade de coleta de experiência | `--num-envs`, só contra o build (`--env`), roda vários ambientes em paralelo. Com `--num-envs=2`, um run sem gráficos levou 52 s, cerca de 1,7 vez mais rápido. No Editor, é sempre um ambiente por vez |
| O jogo roda em time scale 20 por padrão durante o treino | Comportamento esperado, sem ação necessária |
| Interromper o treino no meio poderia perder o modelo | `Ctrl+C` interrompe em 2 a 3 s e ainda exporta o ONNX com o que foi aprendido até ali |
| Máquinas mais lentas não cabem no tempo do módulo. No laboratório do evento, a estimativa, ainda não medida, é de 2 a 4 vezes mais lento que a máquina de referência | Reduzir `max_steps` para caber na janela de tempo combinada |
| Os caminhos usados nos comandos (`--env=builds/...`, `demo_path: Demos/...`) são relativos ao diretório de trabalho | Rodar sempre `mlagents-learn` a partir da raiz do repositório clonado |

### Ambiente

Estes pontos são específicos do projeto FlappyBird e do `FlappyAgent.cs` usados neste tutorial.

| Causa | Correção ou alavanca |
|---|---|
| `EndEpisode()` está comentado no FlappyAgent: o jogo recria o pássaro sozinho ao morrer | Na inferência, a pontuação se lê na interface do próprio jogo, não em uma métrica exposta pelo ML-Agents |
| Recompensa que premia uma ação específica em vez do resultado desejado | Reward hacking: o checklist de observação, ação, recompensa e episódio, e outras armadilhas comuns, estão na Parte 3 de [docs/03-projeto-final.md](03-projeto-final.md) |
| Som de pulo, pontuação e morte tocando em muitas máquinas ao mesmo tempo, em time scale acelerado | O `FlappyScript.cs` zera o volume (`AudioListener.volume = 0`) quando há um treinador conectado (`Academy.Instance.IsCommunicatorOn`). Na inferência, sem treinador, o som continua |
| Os três modelos de currículo, Level1 a Level3, não trocam sozinhos | Arrastar cada ONNX à mão para o campo Model do Behavior Parameters |
| Tutoriais antigos citam o Barracuda ou o Sentis como o pacote que roda os modelos | No Unity 6.3 com o ML-Agents 4.1.0, quem roda o ONNX no editor e nos builds é o Inference Engine (`com.unity.ai.inference` 2.6.1), o novo nome do Sentis |

### Unity

Estes pontos valem só para o Caminho A, com o Editor aberto.

| Causa | Correção ou alavanca |
|---|---|
| A primeira abertura do projeto baixa pacotes e monta a pasta Library | Leva alguns minutos; no laboratório, essa etapa acontece durante o Módulo 0 |
| A pasta Library é gerada localmente em cada máquina | Não é versionada no repositório |
| O projeto fixa a versão 6000.3.22f1 do Editor com `com.unity.ml-agents` 4.1.0 | O laboratório do evento tem a 6000.3.24f1 instalada, duas versões de patch acima da fixada. O Hub pode avisar sobre a diferença, mas o projeto deve abrir normalmente |
| O Caminho A exige login no Editor com uma conta Unity ID | As máquinas do laboratório não têm contas Unity; por isso o Caminho B, sem editor, é o padrão do tutorial |

## O que ficou de fora

A proposta submetida ao SBGames previa 240 min de tutorial. O slot do evento tem 180 min, e a versão final do artigo já descreve as 3 horas. O laboratório prático ficou inteiro, porque é o centro da proposta. Os cortes caíram sobre a imitação completa e o projeto aberto. Os itens abaixo ficaram fora desta versão, mas continuam disponíveis para quem quiser ir além do tutorial ao vivo.

- **PressButton**, o outro ambiente de exemplo do TCC do autor, junto com suas configurações e seus runs de treinamento, cortado por inteiro do escopo deste repositório público.
- A **prática completa do currículo por níveis**: no tutorial ao vivo, Level1 a Level3 é uma demonstração de 3 min no editor, não um treinamento feito pelos participantes.
- **GAIL completo ao vivo**: o Módulo 2 traz leitura crítica das curvas de BC e GAIL já gravadas. Se os instrutores anunciarem a variante, há também um treino curto ao vivo do `il1`. O treino completo de três runs encadeados, como no TCC, fica de fora.
- O **projeto aberto original do Módulo 3**, projetar, implementar e treinar um agente em um ambiente novo do zero: virou material de autoestudo na Parte 3 de [docs/03-projeto-final.md](03-projeto-final.md).

## Próximos passos

- Outros treinadores disponíveis no mlagents 1.1.0, como SAC e MA-POCA, este último voltado a cenários cooperativos com múltiplos agentes.
- Self-play, para ambientes com agentes adversários, treinando o agente contra versões anteriores dele mesmo.
- Currículo por parâmetros de ambiente (Environment Parameters), uma forma de automatizar a progressão de dificuldade além dos três modelos prontos deste tutorial.
- Inference Engine para embarcar modelos treinados em builds finais, fora do editor, o mesmo mecanismo por trás da inferência do FlappyBird treinado neste tutorial.
- O TCC do autor, como referência mais profunda para RL, IL, currículo e os detalhes de implementação do FlappyBird. Ele inclui o ambiente PressButton e os runs deixados de fora deste repositório.

## Referências

- [docs/01-primeiro-agente.md](01-primeiro-agente.md) e [docs/02-imitacao.md](02-imitacao.md): os módulos que produzem os runs `ppo1` e `il1` comparados neste guia.
- TCC do autor: Lucas Brandão Rodrigues, "Aprendizado por Reforço para Desenvolvimento de Jogos: Uma Abordagem prática com Unity ML-Agents", Bacharelado em Inteligência Artificial, Instituto de Informática, Universidade Federal de Goiás (UFG), 2024. O Apêndice 4 traz o material didático sobre o design de ambientes, observações, ações, recompensas e episódios.
- Repositório do projeto do TCC do autor: [Reinforcement Learning with Unity ML-Agents](https://github.com/lucasbrandao4770/Reinforcement-Learning-with-Unity-ML-Agents), onde estão o ambiente PressButton, os runs completos de currículo e os demais experimentos não trazidos para este tutorial.
- Repositório oficial do [Unity ML-Agents Toolkit](https://github.com/Unity-Technologies/ml-agents), a documentação e o código-fonte do framework usado neste tutorial.
- [Manual do pacote com.unity.ml-agents 4.1](https://docs.unity3d.com/Packages/com.unity.ml-agents@4.1/manual/index.html), referência oficial de componentes como Behavior Parameters, sensores e configuração de treino.
- Artigo "Aplicação Prática de Aprendizado por Reforço e Imitation Learning com Unity ML-Agents", de Lucas Brandão Rodrigues, Maria Carolina X. de Almeida e Anna Pietra V. L. B. Moreira, Instituto de Informática, Universidade Federal de Goiás (UFG), SBGames 2026.

Sobre o uso de Inteligência Artificial na produção deste tutorial e deste repositório, veja a seção "Nota sobre uso de IA" no [README.md](../README.md).
