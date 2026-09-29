# Central de treino

## O que é

A Central de treino é o jeito mais simples de seguir o tutorial no laboratório. Ela roda os mesmos comandos do terminal e mostra cada comando na tela. Com ela, você treina um agente, assiste a um modelo já treinado jogando e abre o TensorBoard. Os comandos de terminal continuam nos outros guias. Nas abas Treinar e Assistir, um campo mostra o comando exato que vai rodar, e dá para copiar esse comando.

## Como abrir

### Windows

Dê duplo clique em `central_de_treino.cmd`, na raiz do repositório. Se o ambiente virtual `.venv` ainda não existir, uma janela preta aparece com uma mensagem explicando isso e aponta para `docs/00-instalacao.md`.

### macOS e Linux

Dê duplo clique em `central_de_treino.command`, na raiz do repositório. No macOS, se o sistema bloquear o arquivo por vir de um desenvolvedor não identificado, abra pelo Finder com o botão direito e "Abrir". Se preferir, libere o arquivo em Ajustes do Sistema, Privacidade e Segurança. No Linux, abra um terminal na raiz do repositório e rode `./central_de_treino.command`. Se o `.venv` ainda não existir, a mesma mensagem aparece no terminal, apontando para `docs/00-instalacao.md`.

## A aba Treinar

A aba Treinar cobre o Módulo 1, o primeiro treino do Módulo 2 e o Módulo 3. O segundo e o terceiro treino do Módulo 2 continuam exigindo `--initialize-from` no terminal, como em `docs/02-imitacao.md`, porque esta aba ainda não tem essa opção.

Escolha o arquivo de configuração no menu (o padrão é o do Módulo 1, `python/configs/ppo/FlappyBird_ppo.yaml`), o nome do treino e o build do jogo. O menu mostra só os três arquivos dos módulos. Ao trocar a configuração, o nome do treino muda sozinho para o do módulo (`ppo1`, `il1` ou `ppo2`); um nome digitado depois fica até a próxima troca. O botão `Editar arquivo` abre a configuração escolhida no Bloco de Notas, no Windows, ou no editor de texto padrão do sistema, no macOS e no Linux. O nome do treino só aceita letras, números, `_` e `-`, sem espaço nem acento. Isso acontece porque é o mesmo nome que vira uma pasta em `results/`. O build do jogo é detectado sozinho dentro de `builds/`. Use o botão `Procurar...` se sua cópia estiver em outro lugar. A caixa `Mostrar a janela do jogo` acompanha a configuração escolhida, marcada ou desmarcada do mesmo jeito que os guias mostram para cada módulo, mesmo depois de um nome digitado à mão ou escolhido na janela `Treino já existe`. Desmarque para treinar sem gráficos e mais rápido, do mesmo jeito que `--no-graphics` no terminal. Se já existir uma pasta com esse nome em `results/`, aparece a janela `Treino já existe`. Se essa pasta já tem um modelo salvo, as opções são usar outro nome sugerido automaticamente, continuar esse treino com a configuração atual, recomeçar apagando o anterior, ou cancelar. Se essa pasta não tem nenhum modelo salvo (de uma tentativa que falhou antes de salvar), a janela avisa disso e não oferece continuar: só recomeçar, usar outro nome ou cancelar. Quando o treino termina, a linha de status mostra onde o modelo `.onnx` foi salvo.

## As configurações

Cada treino da Central usa um arquivo de configuração em `python/configs/`. A tabela abaixo explica os três que os módulos do tutorial usam.

| Arquivo de configuração | Módulo | O que treina | Nome do treino | Mostra a janela do jogo | Passos (`max_steps`) | Duração |
|---|---|---|---|---|---|---|
| `FlappyBird_ppo.yaml` | Módulo 1 | Treina o FlappyBird do zero com PPO puro, com a recompensa do próprio jogo. | `ppo1` | Sim | 50 mil | 2 a 3 minutos, com gráficos, num Mac dos autores |
| `FlappyBird_run1.yaml` | Módulo 2 | Treina o FlappyBird com PPO mais Clonagem Comportamental e GAIL, a partir de uma demonstração gravada. | `il1` | Não | 50 mil | 92 segundos, sem gráficos, num Mac dos autores (teste de 24/09) |
| `FlappyBird_desafio.yaml` | Módulo 3 | Treina o FlappyBird com PPO e um hiperparâmetro escolhido por você, para comparar com o `ppo1`. | `ppo2` | Não | 50 mil | 60 a 115 segundos, sem gráficos, num Mac dos autores |

Nas máquinas do laboratório, a estimativa é de 2 a 4 vezes mais lento.

Os outros arquivos em `python/configs/` não aparecem no menu da Central e não são treinos do laboratório. `FlappyBird_run2.yaml` e `FlappyBird_run3.yaml` são o segundo e o terceiro passo da cadeia de imitação do TCC. Eles só fazem sentido continuando o treino anterior com `--initialize-from`, como em `docs/02-imitacao.md`. Servem para quem quiser refazer a cadeia completa em casa. `FlappyBird_ppo_500k.yaml` documenta um treino de referência de 500 mil passos, dez vezes o do `ppo1`. Ele leva cerca de 12 minutos e meio sem gráficos e não cabe no tempo do módulo ao vivo. `Basic_ppo.yaml` treina o ambiente Basic, o "Hello World" do Módulo 1, não o FlappyBird. No dia, é o instrutor quem conduz esse treino, como demonstração de 20 minutos, antes do laboratório do FlappyBird.

## A aba Assistir

Escolha um treino seu que já terminou e clique em Iniciar. O jogo abre e o modelo joga sozinho. Enquanto um treino estiver rodando, a aba Assistir não abre. Clique em Parar e espere o modelo ser salvo. Defina um limite de tempo em minutos, ou marque "Sem limite de tempo" para assistir sem parar sozinho. A velocidade é sempre a normal, a mesma velocidade de quem está jogando. Fechar a janela do jogo também encerra a exibição. A linha de status muda para "O jogo foi fechado. Encerrando...". Quando o processo termina de verdade, ela muda para "O jogo foi fechado. A exibição terminou.", sem precisar clicar em nada. Só aparecem aqui treinos que já passaram por um checkpoint completo. Um treino de referência do repositório, em `results/reference/`, só aparece nesta lista quando também tem esse checkpoint guardado. Ele vem com o prefixo "reference/" no nome, para diferenciar dos seus próprios treinos. Esta aba nunca muda o treino original. Ela grava à parte uma cópia da seção behaviors desse treino e usa essa cópia no comando. Por isso funciona mesmo que o treino tenha sido feito sem gráficos ou com uma rede diferente da do arquivo do repositório. Essa cópia é escrita assim que o treino aparece nesta lista, não só quando você aperta Iniciar. Por isso, o comando mostrado já pode ser copiado e colado a qualquer momento.

## TensorBoard

O botão "TensorBoard" inicia o TensorBoard sozinho e abre a página quando ela estiver pronta, o que leva alguns segundos, sem precisar digitar nada. Se a página não abrir sozinha, rode `tensorboard --logdir results` num terminal, na raiz do repositório e com o ambiente virtual ativo, depois abra `http://localhost:6006`.

## O comando sempre aparece

Acima dos botões de Iniciar e Parar, um campo mostra o comando exato que está prestes a rodar, atualizado conforme você muda as opções. O campo fica vazio se faltar a configuração, o nome do treino ou o build. Na aba Treinar, é o mesmo comando dos docs. Na aba Assistir, a única diferença é o arquivo de configuração: a Central usa a cópia descrita acima, e não `python/configs/ppo/FlappyBird_ppo.yaml`.

## Como parar

O botão `Parar` pede para o treinador parar do jeito certo, exportando o modelo antes de sair, o mesmo efeito de um `Ctrl+C` no terminal. Isso pode levar alguns segundos. Se você clicar em `Parar` enquanto o jogo ainda está abrindo, isso pode levar até um minuto. Para parar um treino, clique em `Parar` e não feche a janela do jogo, porque o treinador abre o jogo de novo. Se depois de 30 segundos o processo ainda não tiver parado, o botão `Forçar parada` fica disponível. Forçar a parada mata o processo na hora, e o modelo desse treino pode não ter sido salvo. Use essa opção só se o `Parar` normal não funcionar. Fechar a janela da Central, com algo rodando, pergunta antes. Treinando, a pergunta é "Um treino está rodando. Parar, salvar o modelo e fechar a Central?". Assistindo, a pergunta é "O modelo está jogando. Parar e fechar?". O botão `Não` deixa tudo como está. O botão `Sim` pede a parada do jeito certo, o mesmo efeito do botão `Parar`, com os mesmos 30 segundos e a opção de forçar. A janela fecha de verdade só quando o processo realmente parar.

## Se algo der errado

Erros comuns aparecem numa caixa curta, em português, dizendo o que fazer. Alguns exemplos: nenhum build encontrado, nome de treino inválido ou nenhum treino salvo ainda para assistir. Quando o treinador para com erro, a linha de status mostra a dica, por exemplo quando outro treino já usa a porta do jogo. Um erro inesperado abre uma janela com uma explicação curta. Os botões `Abrir o log` e `Copiar caminho` nessa janela ajudam a levar o caminho do arquivo de log para quem for te ajudar. O mesmo caminho também fica registrado, selecionável, na área de log da janela principal. O botão `Verificar instalação` roda a checagem do ambiente: na primeira vez pode levar até um minuto, e a área de log termina numa linha como `Resumo: 13 OK, 0 AVISO, 0 FALHA`. O botão `Abrir pasta de resultados` abre a pasta `results/` no gerenciador de arquivos do sistema. Para qualquer problema que a Central não resolva, os comandos de terminal exatos que ela usa estão nos outros guias da pasta `docs/`.
