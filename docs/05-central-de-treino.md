# Central de treino

## O que é

A Central de treino é uma janela simples que roda os mesmos comandos de terminal que o tutorial ensina: treinar um agente, assistir a um modelo já treinado jogando e abrir o TensorBoard. Ela não substitui o terminal. É só uma alternativa para quem prefere clicar em botões. Nas abas Treinar e Assistir, um campo mostra o comando exato que vai rodar, e dá para copiar esse comando.

## Como abrir

### Windows

Dê duplo clique em `central_de_treino.cmd`, na raiz do repositório. Se o ambiente virtual `.venv` ainda não existir, uma janela preta aparece com uma mensagem explicando isso e aponta para `docs/00-instalacao.md`.

### macOS e Linux

Dê duplo clique em `central_de_treino.command`, na raiz do repositório. No macOS, se o sistema bloquear o arquivo por vir de um desenvolvedor não identificado, abra pelo Finder com o botão direito e "Abrir", ou libere em Ajustes do Sistema, Privacidade e Segurança. No Linux, abra um terminal na raiz do repositório e rode `./central_de_treino.command`. Se o `.venv` ainda não existir, a mesma mensagem aparece no terminal, apontando para `docs/00-instalacao.md`.

## A aba Treinar

A aba Treinar cobre o Módulo 1, o primeiro run do Módulo 2 e o Módulo 3; o segundo e o terceiro run do Módulo 2 continuam exigindo `--initialize-from` no terminal, como em `docs/02-imitacao.md`, porque esta aba ainda não tem essa opção.

Escolha o arquivo de configuração no menu (o padrão é o do Módulo 1, `python/configs/ppo/FlappyBird_ppo.yaml`), o nome do treino e o build do jogo. O botão "Editar arquivo" abre a configuração escolhida no editor padrão do sistema, para quem quiser mudar um hiperparâmetro antes de treinar. O nome do treino só aceita letras, números, `_` e `-`, sem espaço nem acento, porque é o mesmo nome que vira uma pasta em `results/`. O build do jogo é detectado sozinho dentro de `builds/`; use o botão "Procurar" se sua cópia estiver em outro lugar. A caixa "Mostrar a janela do jogo" acompanha a configuração escolhida, marcada ou desmarcada do mesmo jeito que os docs mostram para cada módulo; desmarque para treinar sem gráficos e mais rápido, do mesmo jeito que `--no-graphics` no terminal. Se já existir um treino salvo com esse nome, a Central pergunta o que fazer: usar outro nome sugerido automaticamente, continuar esse treino com a configuração atual, recomeçar apagando o anterior, ou cancelar. Quando o treino termina, a linha de status mostra onde o modelo `.onnx` foi salvo.

## A aba Assistir

Escolha, no menu, um treino que já tenha um modelo salvo. Só aparecem aqui treinos que já passaram por um checkpoint completo; um treino de referência do repositório, em `results/reference/`, só aparece nesta lista quando também tem esse checkpoint guardado, e vem com o prefixo "reference/" no nome para diferenciar dos seus próprios treinos. Defina um limite de tempo em minutos, ou marque "Sem limite de tempo" para assistir sem parar sozinho. A velocidade é sempre a normal, a mesma velocidade de quem está jogando. Esta aba nunca muda o treino original. Ela grava à parte uma cópia da seção behaviors desse treino e usa essa cópia no comando. Por isso funciona mesmo que o treino tenha sido feito sem gráficos ou com uma rede diferente da do arquivo do repositório. Essa cópia é escrita assim que o treino aparece nesta lista, não só quando você aperta Iniciar, então o comando mostrado já pode ser copiado e colado a qualquer momento. Fechar a janela do jogo também encerra a exibição: a linha de status muda para "O jogo foi fechado. Encerrando..." e, quando o processo termina de verdade, para "O jogo foi fechado. A exibição terminou.", sem precisar clicar em nada.

## TensorBoard

O botão "TensorBoard" abre `http://localhost:6006` no navegador. Se o TensorBoard ainda não estiver rodando, a Central inicia ele sozinha antes de abrir a página, o que pode levar alguns segundos. Se já houver algo respondendo nessa porta, a Central só abre o navegador direto.

## O comando sempre aparece

Acima dos botões de Iniciar e Parar, um campo mostra o comando exato que está prestes a rodar, atualizado conforme você muda as opções. Na aba Treinar, é o mesmo comando dos docs. Na aba Assistir, a única diferença é o arquivo de configuração: a Central usa a cópia descrita acima, e não `python/configs/ppo/FlappyBird_ppo.yaml`.

## Como parar

O botão "Parar" pede para o treinador parar do jeito certo, exportando o modelo antes de sair, o mesmo efeito de um `Ctrl+C` no terminal. Isso pode levar alguns segundos. Se depois de 30 segundos o processo ainda não tiver parado, o botão "Forçar parada" fica disponível. Forçar a parada mata o processo na hora, e o modelo desse treino pode não ter sido salvo; use só se o "Parar" normal não funcionar. Fechar a janela da Central pergunta antes, se algo estiver rodando: "Um treino está rodando. Parar e fechar?". Cancelar deixa tudo como está. Confirmar pede a parada do jeito certo, o mesmo efeito do botão "Parar", com os mesmos 30 segundos e a opção de forçar; a janela fecha de verdade só quando o processo realmente parar.

## Se algo der errado

Erros comuns aparecem numa caixa curta, em português, dizendo o que fazer: nenhum build encontrado, nome de treino inválido ou nenhum treino salvo ainda para assistir. Quando o treinador para com erro, a linha de status mostra a dica, por exemplo quando a porta do treinador está ocupada. Um erro inesperado abre uma janela com uma explicação curta; os botões "Abrir o log" e "Copiar caminho" nessa janela ajudam a levar o caminho do arquivo de log para quem for te ajudar, e o caminho completo também fica registrado, selecionável, na área de log da janela principal. O botão "Verificar instalação" roda a mesma checagem de `scripts/verify_env.py` e mostra o resultado na área de log da janela. O botão "Abrir pasta de resultados" abre a pasta `results/` no gerenciador de arquivos do sistema. Para qualquer problema que a Central não resolva, os comandos de terminal exatos que ela usa estão nos outros guias da pasta `docs/`.
