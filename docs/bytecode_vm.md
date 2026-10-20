# Bytecode e VM

JSON versão 1 contém robot, register_types e instructions. Cada instrução tem
opcode numérico, args e source opcional [linha,coluna]. Operandos de leitura
são `["c", tipo, valor]` ou `["r", índice]`. Escritas são índices de registrador;
saltos são índices de instrução. Não há LABEL no executável. Os opcodes são
numerados pela lista NAMES em bytecode.py, preservada pelo versionamento.

O gerador faz duas passagens: mapeia símbolos/temporários para registradores
e registra o PC de cada rótulo sem incrementá-lo; então emite instruções com
índices reais. IR e bytecode são diferentes, inclusive em quantidade de
instruções, pois rótulos não são executáveis.

O loader verifica versão estrita (bool não é versão/int), identificação,
limites, estrutura, opcodes, quantidade de operandos, tipos das constantes,
referências de memória, tipos de resultados, sensores e alvos de saltos.
Arquivos externos não passam por pickle ou execução de Python. Limites:
8 MB por arquivo, 50000 instruções, 10000 registradores, fonte de 250000
caracteres, árvore de 100 níveis e 50 diagnósticos. Não há pilha de execução:
esta VM é de registradores. Valores respeitam 4096 bits e 16384 caracteres.
A checagem de tamanho ocorre imediatamente após cada operação (pico transitório
pode ser até o dobro para soma/concatenação e produto de operandos limitados).

A VM copia o programa validado e cria memória própria com os valores padrão.
Mantém PC, registradores, instruções executadas, estado e erro entre ticks.
Decodifica o opcode e aplica COPY, I2F, SENSOR, operações, saltos ou comando.
Cada opcode, incluindo HALT e saltos, consome orçamento. No máximo um comando
por tick; scan também cede. Ao emitir um comando, seu PC já aponta para a
instrução seguinte. Leituras de sensores não cedem, mas gastam orçamento.
VM.tick recebe orçamento entre 1 e 100000 (padrão da arena: 100).

Estados VM: pronta, pausada, finalizada e erro. Estados físicos: ativo,
eliminado e desclassificado. Finalizada não elimina o robô: continua alvo.
Erro aritmético, limite de valor ou argumento dinâmico inválido dá diagnóstico
de execução com origem; a arena desclassifica só aquele robô. Um laço sem
comandos pausa após o orçamento e retoma no próximo tick.

Para comprovar independência, teste_standalone_vm_no_compiler inicia outro
processo que importa apenas bytecode e VM, executa um JSON e verifica que
compiler_arena.parser não foi importado.
