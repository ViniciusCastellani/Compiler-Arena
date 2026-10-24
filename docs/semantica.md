# Tipos, símbolos, expressões e diagnósticos

A gramática completa está em `gramatica.ebnf`. Um arquivo contém exatamente
um robô; todos os corpos exigem chaves e as condições exigem parênteses.

Tipos são int (inteiros Python limitados a 4096 bits), float (IEEE dupla,
finito), bool e string Unicode (até 16384 caracteres). Padrões: 0, 0.0,
false e vazio. Somente int→float é implícito, materializado como I2F na IR.
Bool não é um número da linguagem. Operações numéricas mistas promovem o
int para float antes de operar, também na avaliação constante; igualdade
entre números grandes pode sofrer o arredondamento dessa promoção. `/` sempre retorna float, `%` aceita int
e usa a regra Python: `-5 % 3 == 1`. Não há cast ou coerção de verdade.
`+` concatena somente duas strings. Ordem só compara números; igualdade
compara números entre si ou tipos iguais. Operadores lógicos exigem bool.
Cada nível de ordem/igualdade permite uma comparação; parênteses permitem
combinações explícitas. Não há atribuição como expressão.

Cada bloco abre escopo numerado. Símbolos possuem ID único, nome, tipo, escopo,
mutabilidade, origem e valor constante quando aplicável. IR usa o ID, nunca o
nome como endereço. Declarações só entram no escopo após validar seu
inicializador. Assim `int x=2; {int x=x+1;}` lê o x externo antes de criar o
interno; sem o externo, gera erro. Declarações em laços executam seu COPY de
inicialização em toda passagem. Não há criação dinâmica de registradores.

`const` exige inicializador formado por literais, operadores e constantes já
declaradas, inclusive nos operandos não executados. Não pode receber atribuição
simples ou composta. Duplicidade no mesmo bloco é erro; sombra externa é válida.
Nomes move/back/rotate/scan/fire, os sensores energy/hp/heading/hit e as raízes position/enemy são reservados.

A semântica verifica também código inalcançável, resolve ambos os operandos
e valida seus tipos. Sua avaliação constante não calcula operações no ramo
comprovadamente descartado por curto-circuito: `false && (1/0>0)` é válido.
`false && inexistente` e `false && 1` são inválidos. Literais em si continuam
sujeitos aos limites, mesmo em ramos descartados. Erros de operações totalmente
constantes e avaliadas são de compilação; os dependentes de variáveis são da
VM, inclusive se o otimizador descobrir o valor depois. O otimizador não cria
novos erros de compilação. `runtime.calculate` é compartilhado com a VM.

`+=`, `-=`, `*=` e `/=` verificam tanto a operação quanto a atribuição do
resultado. Por isso int x; x/=2 é inválido. break e continue exigem laço e
atuam no mais interno. continue salta para reavaliar a condição.

Diagnósticos identificam fase e posição. O parser se recupera até `;`/`}`,
a semântica passa ao próximo comando após um erro, com até 50 mensagens.
Um erro interrompe a cadeia antes de gerar executável; declarações inválidas
não entram na tabela, podendo ocasionar diagnóstico posterior de nome ausente.
O exportador remove um bytecode antigo do mesmo diretório se a nova compilação
for inválida. O carregamento e a execução têm categorias próprias de erro.
