# Diagnóstico e rastreabilidade

Foram lidos o PDF de 20 páginas, lexer.py, parser.py, fluxo_lexer_parser.html,
how_to_run.md e os três arquivos em exemplos da base. Os nomes enviados estão
normalizados na pasta original, embora o pedido os cite com sufixos (1)/(2).
Não havia Texto colado.txt adicional, além do próprio pedido anexado.

A base usa máquina de estados, tokens posicionados, descida recursiva, AST,
recuperação por pânico, teto de 50 erros e limite de aninhamento de 100.
Não tem semântica, declaração, VM ou arena. O reconhecimento de int não era
uma regra de declaração. Os exemplos antigos continuam preservados como
registro da linguagem anterior; a nova especificação exige robot e declarações.

| PDF | Módulos responsáveis |
|---|---|
| Linguagem e front-end, pp. 6–9 | lexer.py, parser.py |
| Semântica e tabela, p. 13 | semantic.py |
| IR real, p. 14 | ir.py |
| Pelo menos duas otimizações, p. 15 | optimizer.py |
| Código objeto e VM, p. 16 | codegen.py, bytecode.py, vm.py |
| API, p. 10 | runtime.py, arena.py |
| Arena e ticks, pp. 11–12 | arena.py, vm.py |
| Etapas visíveis, p. 17 | compiler.py, interface.py |
| Entrega e defesa, pp. 18–19 | tests/, docs/, apresentacao/ |

## Extensões do pedido
Tipos float/bool/string, constantes, escopos, break/continue, operadores
compostos, curtos-circuitos, JSON validado, três otimizações, relatórios,
CLI, Tkinter e Pygame em processos separados, testes e slides editáveis.
As regras detalhadas dos 23 itens do pedido são extensões, salvo as capacidades
mínimas identificadas acima. O PDF não fixa os limites numéricos dos comandos.

## Decisões anteriores à implementação da arena
Arena 800×600, coordenadas cartesianas (y cresce para cima), 0° para direita,
ângulos positivos anti-horários. Robôs de raio 12 em círculo de raio 200,
apontados ao centro, energia inicial 100. Até 16 robôs. Scan omnidirecional
até 500 unidades, pelo snapshot inicial; desempate pelo ID. Tiro instantâneo
em raio até 500, acerta o primeiro disco interceptado; dano 10×potência.
Custos: move/back/rotate/scan=1, fire=2×potência. Energia insuficiente:
comando consumido e sem efeito. Energia zero elimina. Movimento linear
simultâneo; trajetórias com discos em contato são canceladas para todos os
envolvidos (até ponto fixo); paredes cancelam o movimento inteiro. Dano e
custos acumulados simultaneamente. Programas terminados permanecem alvos.
Vitória por único elegível; zero é empate; no limite vence a maior energia,
ou empate se houver igualdade. Nenhuma aleatoriedade, semente aceita como
metadado de reprodução. VM com 100 instruções por tick por padrão.

## Revisão das regras de combate

Simulações mostraram que as regras acima premiavam a passividade: energia era
vida e munição sem regeneração, então scan/rotate matavam o próprio robô, e um
programa que fugia para a parede (fora do alcance 500) e parava vencia Alpha,
Beta e Gamma. Tiros instantâneos tornavam as batalhas aritméticas (10 ticks).
Por isso: vida (`hp`) separada de energia regenerável (+1/tick); projéteis a
30/tick que permitem desvio; scan e alcance 1000; sensores `hp`, `heading` e
`hit`; argumentos dinâmicos limitados em vez de desclassificação; movimento
encosta na parede em vez de ser cancelado; término antecipado quando todos os
programas finalizam; desempate por vida. Regras atuais em
[arena_api.md](arena_api.md).

## Alteração posterior solicitada pelo usuário

A interface desktop Tkinter/Pygame foi substituída por HTML/CSS/JavaScript no
navegador, com API HTTP local em Python. Essa preferência posterior substitui
a exigência visual do pedido inicial. O PDF não impõe toolkit. A API dos robôs,
o compilador, os relatórios, a VM e a arena continuam reais e independentes.
