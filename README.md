# Aplicação Prática de Aprendizado por Reforço e Imitation Learning com Unity ML-Agents

Repositório do tutorial do **SBGames 2026** (Goiânia/GO, 29/09 a 02/10/2026), o artefato permanente e citável associado ao trabalho.

*Practical Application of Reinforcement Learning and Imitation Learning with Unity ML-Agents: tutorial artifact for SBGames 2026. All content is in Brazilian Portuguese.*

> [!NOTE]
> **Repositório em construção.** O material será publicado gradualmente até o dia do evento.

## Sobre o tutorial

O tutorial propõe uma abordagem pedagógica estruturada para a transição entre os conceitos teóricos e a implementação prática do Aprendizado por Reforço (*Reinforcement Learning*, RL) e do Aprendizado por Imitação (*Imitation Learning*, IL) no desenvolvimento de jogos, usando o *toolkit* [Unity ML-Agents](https://github.com/Unity-Technologies/ml-agents). São cinco módulos *hands-on*, de complexidade crescente (~4 horas), conduzidos por um ciclo iterativo de **problema → ferramenta → solução**, dos fundamentos do RL à implementação de um projeto completo, passando por técnicas de IL como Clonagem Comportamental (*Behavioral Cloning*, BC) e *Generative Adversarial Imitation Learning* (GAIL).

## O que este repositório vai conter

- **Projetos Unity completos**: os ambientes práticos usados em cada módulo;
- **Códigos-fonte comentados**: agentes, funções de recompensa e configurações de treinamento;
- **Guia de referência**: o registro sistematizado das lições, soluções e "gargalos" práticos documentados ao longo do tutorial;
- **Guia de instalação**: os passos para instalar Python, PyTorch e Unity antes do tutorial (`docs/00-instalacao.md`).

## Módulos

| Módulo | Duração | Desafio proposto |
|--------|---------|------------------|
| 0. Introdução | 30 min | Nivelamento e configuração do ambiente |
| 1. Primeiro agente | 60 min | Agente que aprende a alcançar um alvo ("Hello World") |
| 2. Imitação | 60 min | Tarefa elaborada a partir de demonstrações humanas (BC e GAIL) |
| 3. Projeto final | 75 min | Agente autônomo em jogo ou ambiente simulado complexo |
| 4. Encerramento | 15 min | Síntese, próximos passos e guia de referência |

## Licença

O código deste repositório (scripts C#, scripts Python, configurações de treinamento e o projeto Unity) está sob a licença MIT, no arquivo `LICENSE`. Os textos, a documentação e os materiais didáticos (`README.md`, `docs/` e slides) estão sob a licença Creative Commons Atribuição 4.0 Internacional, no arquivo `LICENSE-docs`.

Exceções: os assets de exemplo da Unity em `unity/SBGamesMLAgents/Assets/SharedAssets/` seguem a licença Apache 2.0 da Unity Technologies, e os sprites e sons do Flappy Bird em `Assets/FlappyBird/Sprites/` e `Assets/FlappyBird/Sounds/` pertencem aos seus autores originais e são usados apenas para fins educacionais. Os detalhes estão em `THIRD_PARTY_NOTICES.md`.

## Autores

Instituto de Informática, Universidade Federal de Goiás (UFG)

- [Lucas Brandão Rodrigues](https://github.com/lucasbrandao4770)
- [Maria Carolina X. de Almeida](https://github.com/mariacxda)
- [Anna Pietra V. L. B. Moreira](https://github.com/pietra-leon)
