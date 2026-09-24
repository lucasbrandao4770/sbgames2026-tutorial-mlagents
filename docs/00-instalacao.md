# Guia de instalação

Este guia é para quem vai instalar o ambiente do tutorial de Unity ML-Agents do SBGames 2026 na
própria máquina, antes do dia 29/09/2026. As máquinas do laboratório do evento são preparadas por
um técnico antes do tutorial. Quem for usar uma máquina do laboratório não precisa deste guia.

Tempo estimado: cerca de 40 minutos no Windows ou no macOS, com uma boa conexão. A maior parte é o
download do Unity Editor.

O tutorial pode ser acompanhado de duas formas.

- **Caminho A (completo).** Unity Editor mais Python. Você clona o repositório, abre o projeto
  Unity e treina os agentes pelo terminal.
- **Caminho B (sem Editor).** Só Python, mais os binários do jogo FlappyBird já compilados para
  Windows. Os binários são distribuídos no dia do tutorial e também pela aba Releases deste
  repositório no GitHub. O Caminho B é mais rápido, porque não baixa o Unity. Como os binários
  são só para Windows, no macOS e no Linux use o Caminho A.

Escolha um caminho antes de instalar. Nas seções de Windows e macOS, os passos que valem só para o
Caminho A estão marcados no título da subseção.

## 1. Resumo da pilha

| Componente | Versão | Caminho A | Caminho B |
|---|---|---|---|
| Unity Hub | 3.20 ou superior | Obrigatório | Não precisa |
| Unity Editor | 6000.3.22f1, licença Personal | Obrigatório | Não precisa |
| Conta Unity ID | - | Obrigatório | Não precisa |
| Pacote `com.unity.ml-agents` | 4.1.0 | Já incluso no projeto | Não precisa |
| Python | 3.10.12 ou 3.10.11 (veja a nota abaixo) | Obrigatório | Obrigatório |
| PyTorch | 2.2.1, versão para CPU | Obrigatório | Obrigatório |
| mlagents (inclui mlagents-envs) | 1.1.0 | Obrigatório | Obrigatório |
| Git, ou download do ZIP | - | Obrigatório | Obrigatório |
| Binários do FlappyBird para Windows | pacote do tutorial | Não precisa | Obrigatório |

O pacote `com.unity.ml-agents` vem declarado no projeto Unity do tutorial. O Unity baixa esse
pacote sozinho na primeira abertura do projeto. Você instala só o Editor.

Sobre o Python: o tutorial foi testado com a versão 3.10.12, mas o python.org não oferece
instalador dela, só o código-fonte. Por isso o guia usa o instalador da 3.10.11, a última versão
3.10 com instalador. O mlagents 1.1.0 aceita qualquer versão de 3.10.1 a 3.10.12.

## 2. Windows 10 ou 11

### 2.1 Unity Hub, Unity ID, licença e Editor (só Caminho A)

O Unity Hub não tem versão em português. Os nomes de menus e botões abaixo estão em inglês, como
aparecem na tela.

1. Baixe e instale o Unity Hub em https://unity.com/download.
2. Abra o Hub e crie uma conta Unity ID, ou entre com uma conta existente.
3. Ao entrar, o Hub costuma ativar a licença Personal sozinho. Para conferir, abra Settings, na
   barra superior, e depois Licenses. Se a lista estiver vazia, clique em Add license e escolha
   "Get a free personal license".
4. Em Installs, clique em Install Editor e escolha a versão 6000.3.22f1. Na tela de módulos,
   deixe tudo desmarcado. Se o Visual Studio vier marcado, desmarque.
5. Se a 6000.3.22f1 não aparecer na lista, abra https://unity.com/releases/editor/archive,
   procure essa versão e clique em Install. O navegador pede para abrir o Hub, que continua a
   instalação.

### 2.2 Python

1. Baixe o instalador do Python 3.10.11 para Windows, o arquivo `python-3.10.11-amd64.exe`, em
   https://www.python.org/downloads/release/python-31011/.
2. Rode o instalador e marque a opção "Add python.exe to PATH" antes de continuar.
3. Confirme a instalação com o inicializador `py`, que vem junto com o Python:

```powershell
py -3.10 --version
```

O retorno deve ser "Python 3.10.11". Se você já tiver outra versão entre 3.10.1 e 3.10.12, ela
também serve.

### 2.3 Repositório

Clone com git:

```powershell
git clone https://github.com/lucasbrandao4770/sbgames2026-tutorial-mlagents.git
cd sbgames2026-tutorial-mlagents
```

Ou baixe o ZIP: na página do repositório no GitHub, clique em "Code" e depois "Download ZIP", e
descompacte em uma pasta onde você tenha permissão de escrita.

### 2.4 Ambiente virtual e pacotes Python

Dentro da pasta do repositório, no PowerShell:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch==2.2.1 --index-url https://download.pytorch.org/whl/cpu
pip install mlagents==1.1.0
mlagents-learn --help
```

Se o PowerShell recusar o `Activate.ps1` com uma mensagem sobre execução de scripts desabilitada,
rode `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, confirme e ative de novo.

O PyTorch vem antes porque o mlagents aceita qualquer torch a partir da 2.1.1, e sem essa ordem o
pip instalaria a versão mais nova, que não foi testada no tutorial.

O comando `mlagents-learn --help` deve imprimir a lista de opções do treinador. Se isso acontecer,
os pacotes Python estão prontos.

### 2.5 Abrir o projeto no Hub (só Caminho A)

1. No Unity Hub, em Projects, abra o menu Add e escolha Add project from disk.
2. Escolha a pasta `unity/SBGamesMLAgents` do repositório clonado.
3. Abra o projeto. Na primeira vez, o Unity baixa pacotes e monta a pasta Library. Isso precisa de
   internet e leva alguns minutos.

## 3. macOS (Apple Silicon)

Os passos gerais são os mesmos do Windows. As diferenças são a instalação do Python e os dois
desvios da subseção 3.3.

### 3.1 Unity Hub, Unity ID, licença e Editor (só Caminho A)

Igual à subseção 2.1. Baixe o Hub para Mac em https://unity.com/download, ative a licença Personal
com uma conta Unity ID e instale a versão 6000.3.22f1 pelo Hub, sem módulos extras.

### 3.2 Python

Duas opções:

- Instalador do python.org: baixe o `python-3.10.11-macos11.pkg` em
  https://www.python.org/downloads/release/python-31011/ e rode o pacote de instalação.
- pyenv, se você já usa:

```bash
pyenv install 3.10.12
pyenv local 3.10.12
```

Confirme a versão:

```bash
python3.10 --version
```

Não use o `python@3.10` do Homebrew. Ele traz uma versão acima da 3.10.12, que o mlagents 1.1.0
recusa.

### 3.3 Desvios conhecidos no macOS

Estes dois problemas foram observados em 23/09/2026, no macOS 26, em Apple Silicon (arm64), com
Python 3.10.12. Os comandos da subseção 3.4 já contornam os dois.

1. O mlagents 1.1.0 exige `grpcio` 1.48.2 ou anterior. Essa versão não tem pacote pronto para
   macOS arm64, e a compilação falha. A saída é instalar primeiro o `grpcio` 1.53.2 e depois o
   mlagents com `--no-deps`, para o pip não trocar o `grpcio`. Como o `--no-deps` também pula as
   outras dependências, elas são instaladas num comando à parte.
2. O `setuptools` 82 ou mais recente não traz mais o módulo `pkg_resources`, que o `mlagents` e o
   `tensorboard` ainda importam. O ambiente testado usa `setuptools<80`. O sintoma, quando isso
   não é feito, é `ModuleNotFoundError: No module named 'pkg_resources'`.

### 3.4 Repositório, ambiente virtual e pacotes Python

```bash
git clone https://github.com/lucasbrandao4770/sbgames2026-tutorial-mlagents.git
cd sbgames2026-tutorial-mlagents
python3.10 -m venv .venv
source .venv/bin/activate
pip install grpcio==1.53.2 "setuptools<80"
pip install torch==2.2.1
pip install --no-deps mlagents==1.1.0 mlagents-envs==1.1.0
pip install "numpy>=1.23.5,<1.24" "protobuf>=3.6,<3.21" onnx==1.15.0 pettingzoo==1.15.0 \
  "cattrs>=1.1.0,<1.7" "gym>=0.21.0" "tensorboard>=2.14" "huggingface-hub>=0.14" \
  h5py pillow pyyaml cloudpickle filelock six attrs
mlagents-learn --help
```

No macOS, o torch do PyPI não tem CUDA, então o índice CPU do Windows não é necessário.

O último `pip install` pode terminar com uma mensagem "ERROR: pip's dependency resolver" sobre o
`grpcio` 1.53.2. Ela é esperada e não impede o funcionamento. Assim como no Windows,
`mlagents-learn --help` deve imprimir a lista de opções do treinador.

### 3.5 Abrir o projeto no Hub (só Caminho A)

Igual à subseção 2.5: no Hub, adicione a pasta `unity/SBGamesMLAgents` do repositório clonado e
abra o projeto.

## 4. Verificação

Com o ambiente virtual ativado, na raiz do repositório:

```bash
python scripts/verify_env.py
```

O script imprime uma linha por checagem, com o resultado OK, AVISO ou FALHA, e um resumo no final.
AVISO pede atenção, mas não impede o tutorial. FALHA precisa ser corrigida antes do dia do
tutorial. Com alguma FALHA, o script sai com código 1 e indica este guia. Sem nenhuma FALHA, o
código de saída é 0. Para ver o resultado em JSON, acrescente `--json` ao comando.

Depois, confirme de novo que o treinador responde:

```bash
mlagents-learn --help
```

Se as duas checagens passarem, a parte Python está pronta. No Caminho A, confira também se o
projeto abre no Editor, como nas subseções 2.5 e 3.5.

## 5. Problemas comuns

- **`ModuleNotFoundError: No module named 'pkg_resources'`.** O ambiente virtual não tem
  setuptools ou tem a versão 82 ou mais recente, que não traz esse módulo. Rode
  `pip install "setuptools<80"` com o ambiente ativado e repita o comando que falhou.
- **Versão errada do Python.** O mlagents 1.1.0 aceita só versões de 3.10.1 a 3.10.12. Confira
  com `python --version`, com o ambiente virtual ativado. Se a versão estiver errada, apague a
  pasta `.venv` e crie o ambiente de novo com o Python certo.
- **PyTorch com CUDA por engano.** No Linux, o torch do PyPI vem com CUDA e ocupa vários GB. No
  Windows, o mesmo acontece com índices de CUDA, como o `cu121`. O tutorial usa só CPU. Para
  trocar, rode `pip uninstall torch` e instale de novo com o índice CPU, como na subseção 2.4.
- **Licença do Unity não ativada.** O Editor pede login ao abrir. Entre no Hub com a conta Unity
  ID e confira a licença em Settings, Licenses, como na subseção 2.1.
- **Hub pede outra versão do Editor.** O projeto usa a versão 6000.3.22f1. Se o Hub avisar que ela
  está faltando, instale essa versão como na subseção 2.1, em vez de abrir o projeto em outra.
  Abra sempre pela pasta `unity/SBGamesMLAgents` do repositório clonado.

## 6. Linux

Não testado pelo autor. Os passos esperados são os do macOS, com duas diferenças. Primeiro, os
desvios da subseção 3.3 são de macOS em Apple Silicon: no Linux, instale o mlagents direto, como
no Windows. Segundo, instale o torch com o índice CPU, também como no Windows, porque o torch do
PyPI para Linux vem com CUDA e ocupa vários GB. No Ubuntu 22.04, o `python3.10` do sistema já é a
3.10.12, mas o `venv` exige o pacote `python3.10-venv`. Em outras distribuições, use o pyenv.
