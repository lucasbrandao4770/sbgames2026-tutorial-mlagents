# Resultados de referência

Curvas de treinamento prontas, para comparar com os runs feitos ao vivo no tutorial. Cada pasta tem só os eventos do TensorBoard, o modelo final em ONNX, o `configuration.yaml` usado e os arquivos JSON de `run_logs/`, sem os checkpoints `.pt`, que não entram no repositório.

- `FlappyBird_ppo/`: PPO puro contra o build do FlappyBird, spike de 24/09/2026 no Mac do Lucas, 50 mil passos, configuração equivalente a `python/configs/ppo/FlappyBird_ppo.yaml`. Referência para comparar com os runs `ppo1` (Módulo 1) e `ppo2` (Módulo 3) do dia.
- `FlappyBird_il_run1/`: run1 de imitação do TCC (2024), recompensa extrínseca fraca e imitação forte (behavioral_cloning 1.0, gail 0.5) com `Level1FlappyAgentDemo.demo`, 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run1.yaml`.
- `FlappyBird_il_run2/`: run2 de imitação do TCC (2024), recompensa extrínseca forte e imitação moderada (behavioral_cloning e gail 0.4) com `Leve2FlappyAgentDemo.demo`, 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run2.yaml`.
- `FlappyBird_il_run3/`: run3 de imitação do TCC (2024), recompensa extrínseca forte e imitação bem fraca (behavioral_cloning e gail 0.1) com `Leve2FlappyAgentDemo.demo`, 50 mil passos, configuração equivalente a `python/configs/imitation/FlappyBird_run3.yaml`.

Para abrir ao lado dos seus próprios runs, rode `tensorboard --logdir results` a partir da raiz do repositório: o TensorBoard lista as quatro pastas acima junto de `ppo1`, `il1` ou `ppo2`, o que permite comparar as curvas lado a lado.
