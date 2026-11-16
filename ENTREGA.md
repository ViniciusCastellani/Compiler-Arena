# Entrega — Compiler Arena

A pasta atual é o projeto completo. O ZIP `entrega_compiler_arena.zip` contém
código, base original, enunciado, exemplos, testes, documentação, relatórios,
capturas reais, PowerPoint editável, notas e PDF de consulta.

## Verificação realizada em 19/10/2026

- Python 3.13.12, Linux: 45 testes unittest aprovados.
- CLI: compilação otimizada e sem otimização, exportação, execução de bytecode
  e batalha Alpha/Beta verificadas.
- VM executada em processo sem importar o parser/compilador.
- Interface HTML validada no Chromium headless: compilação, inspeção, descarte
  de respostas antigas, controles e resultado da batalha, downloads e layout móvel.
- Arena com movimento/rotação suaves, disparos, impactos e eliminações animados;
  velocidade inicial de 1 tick/s, ajustável entre 0,5 e 10 ticks/s.
- Capturas reais da interface HTML incluídas na apresentação.
- 1200 fontes aleatórias malformadas, com semente 2026, passaram pela entrada
  do compilador sem exceção não tratada (ver script de verificação da entrega).
- 18 slides PPTX com notas e diagramas editáveis. Renderizações revisadas e
  medidas; sem cortes/sobreposições de texto detectados pelo renderizador local.

Os resultados completos estão em `artefatos/testes.txt`, `teste_web.txt` e
`batalha.json`. O exemplo isolado otimizacao.robo reduz a IR de 5 para 3
instruções (40%); não é uma medição de velocidade. Alpha/Beta terminou com
vitória de Alpha no tick 10, orçamento 100, otimizações ligadas, limite 300.

## Abrir

```bash
python main.py web
```

Sem interface e sem dependências externas:

```bash
python main.py compile exemplos/alpha.robo --out artefatos/alpha
python main.py compile exemplos/beta.robo --out artefatos/beta
python main.py battle artefatos/alpha/robot.rbc.json artefatos/beta/robot.rbc.json --ticks 300
python -m unittest discover -s tests -v
```

Veja README.md e docs/defesa_demonstracao.md para o roteiro completo.

## Limites reais

A interface agora é HTML no navegador, servida por Python em localhost:8000.
Não exige Tkinter ou Pygame. Windows está documentado, mas não foi testado.
O PDF dos slides é rasterizado pelo gerador local, não exportado pelo Office;
fontes e layout devem ser confirmados na máquina de apresentação. O PPTX é
editável. A otimização garante transformações locais conservadoras; não se
promete cronologia idêntica das batalhas com/sem otimização. As exclusões
propositais da linguagem e as decisões da arena estão em docs/limitacoes.md.
