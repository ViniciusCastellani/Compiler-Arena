# Arquitetura e reaproveitamento

O pacote `compiler_arena` separa o compilador, o executor e a interface visual.
`main.py` fornece a CLI. Nenhuma etapa do núcleo depende de Tkinter, Pygame ou
python-pptx. O front-end **do compilador** compreende lexer, parser e semântica;
a interface **visual** é o aplicativo editor/arena.

| Etapa | Entrada | Saída efetivamente consumida |
|---|---|---|
| Lexer | texto UTF-8 | tokens posicionados |
| Parser | tokens | AST com origem |
| Semântica | AST | AST anotada + símbolos |
| Builder de IR | AST validada | quádruplas tipadas |
| Otimizador | IR original | nova IR + log + CFG |
| Gerador | IR selecionada | registradores e saltos numéricos |
| VM | bytecode validado + snapshot | até um comando por tick |
| Arena | comandos simultâneos | novo estado e scans |

## Código original
Os arquivos originais continuam intocados em `analisador_lexico-sintatico/`.
O lexer foi copiado e ampliado: preserva Token, Enum, cursor, `_peek`, `_advance`,
tratamento CRLF, identificação ASCII, scanners, tabela de tokens e CLI.
`next_token`, números e strings receberam comentários, floats, operadores e
validação estrita de escapes. O scanner antigo de comparação não é mais usado
pela nova seleção, mas permanece para comparação didática. A documentação do
scanner de string foi corrigida para não sugerir aceitação de escapes arbitrários.

O parser preserva ASTNode (ampliado com line/column/meta), SyntaxErrorInfo,
ParserError, helpers de consumo/lookahead, contexto `_nesting`, teto de erros,
formatação, JSON e CLI. As regras de gramática foram substituídas pelas regras
RoboLang: a evolução é substancial porque antes só havia atribuição e if.
A recuperação foi adaptada para preservar `}` ao sincronizar, sem travar.
Todas as fases posteriores foram adicionadas, e não atribuídas à base anterior.

## Integração visual HTML

A interface agora está em `compiler_arena/web/index.html`, `style.css` e `app.js`.
O servidor `web_server.py` usa ThreadingHTTPServer local e biblioteca padrão.
O front-end envia fonte e opção de otimização e recebe o relatório completo.
Uma revisão por editor invalida resultados e descarta respostas antigas.
O hash SHA-256 e a fonte exata são exportados juntos. Robôs adicionados à
lista de batalha preservam a versão compilada.

O servidor mantém uma Arena por sessão do navegador, protegida por lock.
Cada passo HTTP chama Arena.step uma vez e devolve o snapshot. O canvas só
desenha esse snapshot: não reimplementa VM, física ou regras de combate.
O agendamento no cliente aguarda o passo terminar e só então agenda o próximo.
Pausa impede novos passos; reinício substitui a Arena preservando programas,
limite e orçamento. Exportação recebe os logs completos do servidor.

Inteiros fora dos 53 bits seguros do JavaScript usam um objeto de transporte
`{"$integer":"valor decimal"}`. O Python decodifica antes de validar/executar;
o exportador JavaScript grava os dígitos como números no JSON final. Floats
usam `{"$float":"450.0"}` no transporte para preservar o tipo mesmo quando
não há parte fracionária. Snapshots são convertidos para números apenas
para a renderização no canvas. Arquivos
externos de bytecode são analisados no Python, evitando arredondamento no upload.

Tkinter foi substituído a pedido do usuário. Pygame permanece apenas como
visualizador opcional da CLI `battle --visual`; a interface web não depende dele.
