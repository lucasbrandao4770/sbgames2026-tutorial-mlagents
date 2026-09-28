# Central de treino

## O que é

A Central de treino é uma janela simples que roda os mesmos comandos de terminal que o tutorial ensina: treinar um agente, assistir a um modelo já treinado jogando e abrir o TensorBoard.
Ela não substitui o terminal, só evita ele para quem prefere clicar em botões.
Toda ação mostra o comando exato que vai rodar, num campo que dá para copiar, para quem quiser reproduzir por conta própria depois.

## Como abrir

### Windows

Dê duplo clique em `central_de_treino.cmd`, na raiz do repositório.
Se o ambiente virtual `.venv` ainda não existir, uma janela preta aparece com uma mensagem explicando isso e aponta para `docs/00-instalacao.md`.

### macOS e Linux

Dê duplo clique em `central_de_treino.command`, na raiz do repositório.
No macOS, se o sistema bloquear o arquivo por vir de um desenvolvedor não identificado, abra pelo Finder com o botão direito e "Abrir", ou libere em Ajustes do Sistema, Privacidade e Segurança.
Se o `.venv` ainda não existir, o Terminal abre com a mesma mensagem apontando para `docs/00-instalacao.md`.

## A aba Treinar

Escolha o arquivo de configuração no menu (o padrão é o do Módulo 1, `python/configs/ppo/FlappyBird_ppo.yaml`), o nome do treino e o build do jogo.
O botão "Editar arquivo" abre a configuração escolhida no editor padrão do sistema, para quem quiser mudar um hiperparâmetro antes de treinar.
O nome do treino só aceita letras, números, `_` e `-`, sem espaço nem acento, porque é o mesmo nome que vira uma pasta em `results/`.
O build do jogo é detectado sozinho dentro de `builds/`; use o botão "Procurar" se sua cópia estiver em outro lugar.
A caixa "Mostrar a janela do jogo" fica marcada por padrão; desmarque para treinar sem gráficos e mais rápido, do mesmo jeito que `--no-graphics` no terminal.
Se já existir um treino salvo com esse nome, a Central pergunta o que fazer: continuar esse treino, recomeçar apagando o anterior, ou cancelar.
Quando o treino termina, a linha de status mostra onde o modelo `.onnx` foi salvo.

## A aba Assistir

Escolha, no menu, um treino que já tenha um modelo salvo.
Só aparecem aqui treinos que já passaram por um checkpoint completo; um treino de referência do repositório, em `results/reference/`, só aparece nesta lista quando também tem esse checkpoint guardado, e vem com o prefixo "reference/" no nome para diferenciar dos seus próprios treinos.
Defina um limite de tempo em minutos, ou marque "Sem limite de tempo" para assistir sem parar sozinho.
A velocidade é sempre a normal, a mesma velocidade de quem está jogando.
Esta aba nunca muda o treino original: ela cria uma configuração à parte, só com a rede do modelo escolhido, então funciona mesmo que esse treino tenha sido feito sem gráficos.
Fechar a janela do jogo também encerra a exibição: a linha de status mostra "Encerrando..." por alguns segundos e depois volta ao normal, sem precisar clicar em nada.

## TensorBoard

O botão "TensorBoard" abre `http://localhost:6006` no navegador.
Se o TensorBoard ainda não estiver rodando, a Central inicia ele sozinha antes de abrir a página, o que pode levar alguns segundos.
Se já houver algo respondendo nessa porta, a Central só abre o navegador direto.

## O comando sempre aparece

Acima dos botões de Iniciar e Parar, um campo mostra o comando exato que está prestes a rodar, atualizado conforme você muda as opções.
O botão "Copiar comando" copia esse texto, pronto para colar num terminal na raiz do repositório, com o ambiente virtual ativo.
É a mesma forma que os docs ensinam: quem quiser aprender o terminal pode acompanhar aqui e repetir por fora, sem depender da Central.

## Como parar

O botão "Parar" pede para o treinador parar do jeito certo, exportando o modelo antes de sair, o mesmo efeito de um `Ctrl+C` no terminal.
Isso pode levar alguns segundos.
Se depois de 30 segundos o processo ainda não tiver parado, o botão "Forçar parada" aparece.
Forçar a parada mata o processo na hora, e o modelo desse treino pode não ter sido salvo; use só se o "Parar" normal não funcionar.
Fechar a janela da Central para automaticamente o que estiver rodando, do mesmo jeito.

## Se algo der errado

Erros comuns aparecem numa caixa curta, em português, dizendo o que fazer: nenhum build encontrado, nome de treino inválido, nenhum treino salvo ainda para assistir, ou a porta do treinador ocupada.
Um erro inesperado abre uma janela com uma explicação curta e o caminho do arquivo de log completo, num campo que dá para selecionar e copiar; os botões "Abrir o log" e "Copiar caminho" ajudam a levar essa informação para quem for te ajudar. O caminho também fica registrado na área de log da janela principal.
O botão "Verificar instalação" roda a mesma checagem de `scripts/verify_env.py` e mostra o resultado na área de log da janela.
O botão "Abrir pasta de resultados" abre a pasta `results/` no gerenciador de arquivos do sistema.
Para qualquer problema que a Central não resolva, os comandos de terminal exatos que ela usa estão nos outros guias da pasta `docs/`.
