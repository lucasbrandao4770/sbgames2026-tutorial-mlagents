# Central de treino

## O que é

A Central de treino é uma janela simples que roda os mesmos comandos de terminal que o tutorial ensina. Ela treina um agente, assiste a um modelo já treinado jogando e abre o TensorBoard. Ela não substitui o terminal. É só uma alternativa para quem prefere clicar em botões. Nas abas Treinar e Assistir, um campo mostra o comando exato que vai rodar, e dá para copiar esse comando.

## Como abrir

### Windows

Dê duplo clique em `central_de_treino.cmd`, na raiz do repositório. Se o ambiente virtual `.venv` ainda não existir, uma janela preta aparece com uma mensagem explicando isso e aponta para `docs/00-instalacao.md`.

### macOS e Linux

Dê duplo clique em `central_de_treino.command`, na raiz do repositório. No macOS, se o sistema bloquear o arquivo por vir de um desenvolvedor não identificado, abra pelo Finder com o botão direito e "Abrir". Se preferir, libere o arquivo em Ajustes do Sistema, Privacidade e Segurança. No Linux, abra um terminal na raiz do repositório e rode `./central_de_treino.command`. Se o `.venv` ainda não existir, a mesma mensagem aparece no terminal, apontando para `docs/00-instalacao.md`.

## A aba Treinar

A aba Treinar cobre o Módulo 1, o primeiro run do Módulo 2 e o Módulo 3. O segundo e o terceiro run do Módulo 2 continuam exigindo `--initialize-from` no terminal, como em `docs/02-imitacao.md`, porque esta aba ainda não tem essa opção.

Escolha o arquivo de configuração no menu (o padrão é o do Módulo 1, `python/configs/ppo/FlappyBird_ppo.yaml`), o nome do treino e o build do jogo. O botão "Editar arquivo" abre a configuração escolhida no editor padrão do sistema, para quem quiser mudar um hiperparâmetro antes de treinar. O nome do treino só aceita letras, números, `_` e `-`, sem espaço nem acento. Isso acontece porque é o mesmo nome que vira uma pasta em `results/`. O build do jogo é detectado sozinho dentro de `builds/`. Use o botão "Procurar" se sua cópia estiver em outro lugar. A caixa "Mostrar a janela do jogo" acompanha a configuração escolhida, marcada ou desmarcada do mesmo jeito que os docs mostram para cada módulo. Desmarque para treinar sem gráficos e mais rápido, do mesmo jeito que `--no-graphics` no terminal. Se já existir um treino salvo com esse nome, a Central pergunta o que fazer. As opções são usar outro nome sugerido automaticamente, continuar esse treino com a configuração atual, recomeçar apagando o anterior, ou cancelar. Quando o treino termina, a linha de status mostra onde o modelo `.onnx` foi salvo.

## As configurações

Cada treino da Central usa um arquivo de configuração em `python/configs/`. A tabela abaixo explica os três que os módulos do tutorial usam.

| Arquivo de configuração | Módulo | O que treina | Nome do treino | Mostra a janela do jogo | Passos (`max_steps`) | Duração |
|---|---|---|---|---|---|---|
| `FlappyBird_ppo.yaml` | Módulo 1 | Treina o FlappyBird do zero com PPO puro, com a recompensa do próprio jogo. | `ppo1` | Sim | 50 mil | 2 a 3 minutos, com gráficos, na máquina de referência |
| `FlappyBird_run1.yaml` | Módulo 2 | Treina o FlappyBird com PPO mais Clonagem Comportamental e GAIL, a partir de uma demonstração gravada. | `il1` | Não | 50 mil | 92 segundos, sem gráficos, na máquina de referência (teste de 24/09) |
| `FlappyBird_desafio.yaml` | Módulo 3 | Treina o FlappyBird com PPO e um hiperparâmetro escolhido por você, para comparar com o `ppo1`. | `ppo2` | Não | 50 mil | 75 a 115 segundos, sem gráficos, na máquina de referência |

Os outros arquivos em `python/configs/` não pertencem a nenhum dos três módulos. `FlappyBird_run2.yaml` e `FlappyBird_run3.yaml` são o segundo e o terceiro passo da cadeia de imitação do TCC. Eles só fazem sentido continuando o treino anterior com `--initialize-from`, como em `docs/02-imitacao.md`. Servem para quem quiser refazer a cadeia completa em casa. `FlappyBird_ppo_500k.yaml` documenta um treino de referência de 500 mil passos, dez vezes o do `ppo1`. Ele leva cerca de 12 minutos e meio sem gráficos e não cabe no tempo do módulo ao vivo. `Basic_ppo.yaml` treina o ambiente Basic, o "Hello World" do Módulo 1, não o FlappyBird. No dia, é o instrutor quem conduz esse treino, como demonstração de 20 minutos, antes do laboratório do FlappyBird.

## A aba Assistir

Escolha, no menu, um treino que já tenha um modelo salvo. Só aparecem aqui treinos que já passaram por um checkpoint completo. Um treino de referência do repositório, em `results/reference/`, só aparece nesta lista quando também tem esse checkpoint guardado. Ele vem com o prefixo "reference/" no nome, para diferenciar dos seus próprios treinos. Defina um limite de tempo em minutos, ou marque "Sem limite de tempo" para assistir sem parar sozinho. A velocidade é sempre a normal, a mesma velocidade de quem está jogando. Esta aba nunca muda o treino original. Ela grava à parte uma cópia da seção behaviors desse treino e usa essa cópia no comando. Por isso funciona mesmo que o treino tenha sido feito sem gráficos ou com uma rede diferente da do arquivo do repositório. Essa cópia é escrita assim que o treino aparece nesta lista, não só quando você aperta Iniciar. Por isso, o comando mostrado já pode ser copiado e colado a qualquer momento. Fechar a janela do jogo também encerra a exibição. A linha de status muda para "O jogo foi fechado. Encerrando...". Quando o processo termina de verdade, ela muda para "O jogo foi fechado. A exibição terminou.", sem precisar clicar em nada.

## TensorBoard

O botão "TensorBoard" inicia o TensorBoard sozinho e abre a página quando ela estiver pronta, o que leva alguns segundos, sem precisar digitar nada. Se a página não abrir sozinha, rode `tensorboard --logdir results` num terminal, na raiz do repositório e com o ambiente virtual ativo, depois abra `http://localhost:6006`.

## O comando sempre aparece

Acima dos botões de Iniciar e Parar, um campo mostra o comando exato que está prestes a rodar, atualizado conforme você muda as opções. Na aba Treinar, é o mesmo comando dos docs. Na aba Assistir, a única diferença é o arquivo de configuração: a Central usa a cópia descrita acima, e não `python/configs/ppo/FlappyBird_ppo.yaml`.

## Como parar

O botão "Parar" pede para o treinador parar do jeito certo, exportando o modelo antes de sair, o mesmo efeito de um `Ctrl+C` no terminal. Isso pode levar alguns segundos. Se depois de 30 segundos o processo ainda não tiver parado, o botão "Forçar parada" fica disponível. Forçar a parada mata o processo na hora, e o modelo desse treino pode não ter sido salvo. Use essa opção só se o "Parar" normal não funcionar. Fechar a janela da Central pergunta antes, se algo estiver rodando: "Um treino está rodando. Parar e fechar?". Cancelar deixa tudo como está. Confirmar pede a parada do jeito certo, o mesmo efeito do botão "Parar", com os mesmos 30 segundos e a opção de forçar. A janela fecha de verdade só quando o processo realmente parar.

## Se algo der errado

Erros comuns aparecem numa caixa curta, em português, dizendo o que fazer. Alguns exemplos: nenhum build encontrado, nome de treino inválido ou nenhum treino salvo ainda para assistir. Quando o treinador para com erro, a linha de status mostra a dica, por exemplo quando a porta do treinador está ocupada. Um erro inesperado abre uma janela com uma explicação curta. Os botões "Abrir o log" e "Copiar caminho" nessa janela ajudam a levar o caminho do arquivo de log para quem for te ajudar. O caminho completo também fica registrado, selecionável, na área de log da janela principal. O botão "Verificar instalação" roda a mesma checagem de `scripts/verify_env.py` e mostra o resultado na área de log da janela. O botão "Abrir pasta de resultados" abre a pasta `results/` no gerenciador de arquivos do sistema. Para qualquer problema que a Central não resolva, os comandos de terminal exatos que ela usa estão nos outros guias da pasta `docs/`.
