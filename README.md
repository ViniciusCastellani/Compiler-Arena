# Compiler Arena

Compilador acadêmico RoboLang em Python 3.11+, com cadeia real:
fonte → tokens → AST → semântica → IR → otimização → bytecode → VM → arena.
Os códigos originais estão preservados. Comece por [diagnóstico e requisitos](docs/requisitos.md).

## Instalação

A interface HTML, a CLI e os testes do núcleo usam somente a biblioteca padrão.
Para abrir o editor e a arena no navegador:

```bash
python main.py web
```

Acesse **http://127.0.0.1:8000**. O navegador abre automaticamente. Para escolher
outra porta: `python main.py web --port 8080`. Para apenas iniciar o servidor:
`python main.py web --no-browser`. Encerre com Ctrl+C. O comando antigo
`python main.py gui` também abre a interface HTML.

Não é necessário Tkinter, Pygame, Node ou npm para a interface web. Pygame
continua opcional para `battle --visual`; `requirements.txt` instala essa opção.
A aplicação é local: o compilador, a VM e a arena continuam em Python; HTML,
CSS e JavaScript cuidam do editor, das abas e da renderização do canvas.
Não abra index.html diretamente, pois as ações precisam da API local.

No Linux pode usar `python3`. No Windows, use Python 3.11+ de python.org.
Opcionalmente crie um ambiente: `python -m venv .venv`, ative com
`source .venv/bin/activate` (Linux) ou `.venv\Scripts\Activate.ps1` (PowerShell).

## Editor e batalha no navegador

Compile Alpha, adicione à batalha; abra Beta, compile, adicione. Marque ambos,
prepare a arena e use Iniciar/Pausar/Um tick/Reiniciar. A batalha começa em
1 tick/s, com movimento, rotação, disparos e impactos animados. O controle de
velocidade permite acompanhar mais devagar (0,5 tick/s) ou acelerar. As etapas reais estão
nas abas. Exportar relatório baixa fonte, hash e todas as etapas em JSON;
Baixar bytecode exporta o executável. Abrir/Salvar usa os arquivos e downloads
do navegador. Carregar bytecode permite usar programas previamente compilados.

## Compilação, exportação e execução

```bash
python main.py compile exemplos/alpha.robo --out artefatos/alpha
python main.py compile exemplos/alpha.robo --no-opt --out artefatos/alpha_sem_opt
python main.py compile exemplos/beta.robo --out artefatos/beta
python main.py compile exemplos/gamma.robo --out artefatos/gamma
python main.py run artefatos/alpha/robot.rbc.json --ticks 100 --budget 100
python main.py battle artefatos/alpha/robot.rbc.json artefatos/beta/robot.rbc.json --ticks 300 --budget 100 --seed 0 --out artefatos/batalha.json
python main.py battle artefatos/alpha/robot.rbc.json artefatos/beta/robot.rbc.json --ticks 300 --visual
python -m compiler_arena.lexer exemplos/alpha.robo
python -m compiler_arena.parser exemplos/alpha.robo --ast-json artefatos/ast.json
```

`run` usa sensores controlados (energy=100, posição=0, sem inimigo) para
experimentos de VM. `battle` executa os sensores físicos da arena.
A CLI retorna 0 em sucesso, 1 por erro de compilação/execução e 2 por erro de
arquivo/argumento/carregamento. Uma desclassificação em batalha é resultado
da simulação e não uma falha global do comando.

## Validação e apresentação

```bash
python -m unittest discover -s tests -v
# Opcional: automação do navegador e capturas
python -m pip install -r ferramentas/requirements-testes.txt
python -m playwright install chromium
python ferramentas/verificar_web.py
# Geração dos slides
python -m pip install -r apresentacao/requirements.txt
python apresentacao/gerar_apresentacao.py
python ferramentas/empacotar.py
```

O teste web usa Chromium headless; não requer tela ou Xvfb. Consulte
[a interface e os testes](docs/interface_testes.md) e [a apresentação](apresentacao/README.md).

## Documentação

- [Arquitetura e reaproveitamento](docs/arquitetura.md)
- [Gramática EBNF](docs/gramatica.ebnf)
- [Tipos, símbolos, escopos e diagnósticos](docs/semantica.md)
- [IR, otimizações e CFG](docs/ir_otimizacao.md)
- [Bytecode, VM e limites](docs/bytecode_vm.md)
- [API, sensores e regras da arena](docs/arena_api.md)
- [Interface e testes](docs/interface_testes.md)
- [Defesa e roteiro da demonstração](docs/defesa_demonstracao.md)
- [Limitações reais](docs/limitacoes.md)

A entrega inclui exemplos válidos, três estratégias e erros por fase;
artefatos inspecionáveis; PPTX editável e ZIP reproduzível. As métricas são
contagens de instruções IR, não velocidade medida.
