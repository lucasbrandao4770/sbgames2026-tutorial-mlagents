# Demos

Duas gravações de demonstração humana do FlappyBird, usadas pelos treinos de Clonagem Comportamental (BC) e GAIL do Módulo 2.

- `Level1FlappyAgentDemo.demo`: gravada no nível 1 do FlappyBird, usada pelo run1 (`python/configs/imitation/FlappyBird_run1.yaml`).
- `Leve2FlappyAgentDemo.demo`: gravada no nível 2, usada pelos runs 2 e 3 (`FlappyBird_run2.yaml`, `FlappyBird_run3.yaml`). O nome tem um erro de digitação original do TCC, falta o "l" de "Level", e a grafia foi mantida porque os dois yamls apontam para esse nome exato.

As duas foram gravadas no editor Unity com o componente Demonstration Recorder, durante o TCC (2024) dos autores, e são cópias binárias idênticas às de `unity/SBGamesMLAgents/Assets/FlappyBird/Demos/`.

Os yamls de imitação referenciam `demo_path` como `Demos/<arquivo>.demo`, relativo ao diretório de trabalho. Por isso todo comando `mlagents-learn` que usa esses yamls precisa rodar a partir da raiz deste repositório.
