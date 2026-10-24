# Limitações e decisões de escopo

A linguagem deliberadamente não tem funções, arrays, importação, for, casts,
notação científica, ++/--, recursão ou comentários aninhados. Escopo é léxico,
mas registradores são alocados estaticamente e reutilizados por declaração.
O otimizador não faz propagação global, SSA, eliminação geral de código morto
ou prova de término. Não há medição de ganho de tempo ou promessa de batalha
idêntica entre otimização ligada/desligada.

Combate usa projéteis em linha reta com velocidade constante e movimento
linear por tick, sem física inercial, dano de colisão ou obstáculos internos.
Scan omnidirecional pode envelhecer até o próximo comando, e não há sensor de
projéteis em voo (só `hit`, depois do impacto). Não há aleatoriedade atualmente.

A interface HTML tem um arquivo por editor, sem realce completo de sintaxe ou
depurador por instrução. Diagnósticos levam à linha no editor. Salvar baixa o
arquivo em vez de sobrescrever diretamente o disco. A página requer o servidor
local Python; abrir o HTML isolado não executa o compilador. O serviço é local,
sem contas, persistência de sessões após encerramento ou hospedagem pública.
A pausa impede novos ticks; um passo em trânsito pode terminar.

A validação de bytecode evita acesso arbitrário/execução de código hospedeiro,
mas não pretende substituir isolamento de sistema operacional contra usuários
maliciosos. Arquivos são limitados e a VM controla instruções e tamanhos de valor.

A interface foi validada no Chromium headless em Linux, incluindo largura móvel.
Windows e outros navegadores não foram executados neste ambiente. Detalhes da
renderização dos slides/PDF ficam em apresentacao/README.md.
