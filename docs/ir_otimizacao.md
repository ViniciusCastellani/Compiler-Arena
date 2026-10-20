# IR, CFG e otimizações

Operand é uma estrutura com kind, value e type. Categorias explícitas:
constant, symbol, temporary e label. Quad contém op/arg1/arg2/result,
tipo do resultado e linha/coluna. A IR não interpreta convenções em strings
como se fossem endereços. Apenas as operações têm nomes textuais.

COPY representa inicializações e atribuições. I2F explicita a promoção.
BIN:+/-/*/... e UN:!/+/- são tipados pelos operandos e pelo destino.
SENSOR mantém uma leitura explícita; CMD:move/etc. mantém os efeitos.
LABEL, JMP, JZ e JNZ representam controle; HALT finaliza. Strings usam BIN:+,
BIN:== e BIN:!=, com o tipo string registrado nos operandos.

`if (c) { A } else { B }` traduz-se em JZ c, Lelse; A; JMP Lfim;
LABEL Lelse; B; LABEL Lfim. `while (c) { A }` usa LABEL Linicio; cálculo de c;
JZ c,Lfim; A; JMP Linicio; LABEL Lfim. break aponta Lfim e continue Linicio.
`a && b` copia a para t, faz JZ t,Lfim, avalia b e copia para t. `||` usa JNZ.
Assim a direita não é executada quando a esquerda decide o resultado.

`ir.validate` checa categorias e rótulos e usa o contrato do gerador/validador
de bytecode para tipos, quantidade de operandos e destinos. A exportação
entrega IR original/otimizada em JSON e texto, mais CFG e log.

## Três técnicas
1. Constant folding: BIN/UN/I2F com entradas constantes viram COPY constante.
2. Simplificação algébrica: int x+0, x-0, x*1 viram COPY x.
3. Propagação local: substitui símbolos/temporários conhecidos por constantes
   apenas dentro do bloco básico. Uma escrita invalida o destino antes de
   registrar o novo valor. Não há estado propagado por arestas do CFG.

Líderes: primeira instrução, rótulos e sucessores de saltos/HALT/comandos.
Sucessores registram alvo e/ou queda sequencial. Comandos delimitam blocos por
conservadorismo. O otimizador preserva a original com deepcopy. Como limpeza,
remove apenas COPY para temporário sem uso, cuja avaliação de entrada já
ocorreu. Nenhuma operação possivelmente falha é eliminada.

Não se removem/reordenam comandos, leituras de sensores, divisões ou produtos
por zero. Não há x/x→1. Identidades de int não são estendidas a float.
Falha ao dobrar preserva a operação e seu erro dinâmico. Não há cálculo de
operações em uma cauda comprovadamente descartada dentro do bloco.
Nos outros blocos pode haver dobramento de operações seguras, nunca emissão
de um novo erro de compilação. Saltos de curto-circuito permanecem explícitos.

Métricas são contagem de instruções IR (incluindo rótulos) antes/depois e
redução percentual, não medição de velocidade. Como cada opcode consome
orçamento por tick, a otimização pode mudar o instante de uma ação. Os testes
comparam sequência de ações e erros com sensores controlados, não prometem
igualdade temporal de batalhas. Para demonstrar essa diferença, use budget=1.
