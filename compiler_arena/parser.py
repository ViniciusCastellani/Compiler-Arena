"""
    Analisador sintático
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

from .lexer import Lexer, Token, TokenType, render_token_table


MAX_NESTING_DEPTH = 100
"""Limite de níveis de aninhamento aceitos pelo parser.

Cada nível consome quadros da pilha do Python, e o limite converte um possível
estouro de pilha em um erro de sintaxe comum, com linha e coluna.
"""

MAX_REPORTED_ERRORS = 50
"""Teto de erros reportados, atingido apenas por arquivos muito malformados."""

_RELATIONAL_OPERATORS = (
    TokenType.OP_IGUAL,
    TokenType.OP_DIFERENTE,
    TokenType.OP_MENOR,
    TokenType.OP_MENOR_IGUAL,
    TokenType.OP_MAIOR,
    TokenType.OP_MAIOR_IGUAL,
)
"""Tipos aceitos por <op_relacional>, na ordem em que aparecem na gramática."""


@dataclass
class ASTNode:
    """Nó da árvore sintática abstrata.

    Attributes:
        tipo: Categoria do nó, como "PROGRAMA", "ATRIBUICAO" ou "NUMERO".
        valor: Operador, nome ou literal associado ao nó, quando houver.
        filhos: Subárvores do nó, na ordem de leitura do código-fonte.
    """

    tipo: str
    valor: str | int | None = None
    filhos: list["ASTNode"] = field(default_factory=list)

    line: int = 1
    column: int = 1
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Converte o nó e suas subárvores em dicionários.

        Returns:
            O nó em um formato serializável em JSON.
        """
        return {
            "line": self.line, "column": self.column, "meta": self.meta,
            "tipo": self.tipo,
            "valor": self.valor,
            "filhos": [child.to_dict() for child in self.filhos],
        }


@dataclass
class SyntaxErrorInfo:
    """Erro de análise localizado no código-fonte.

    Attributes:
        message: Descrição do erro, já classificado como léxico ou sintático.
        line: Linha do token que interrompeu a análise.
        column: Coluna do token que interrompeu a análise.
        lexeme: Lexema desse token, ou "EOF" no fim do código-fonte.
    """

    message: str
    line: int
    column: int
    lexeme: str


@dataclass
class AnalysisResult:
    """Resultado completo da análise de um código-fonte.

    Attributes:
        tokens: Tokens produzidos pelo lexer, inclusive os de tipo ERRO.
        ast: Árvore sintática do programa, ou None se houver erros.
        errors: Erros encontrados, na ordem em que ocorreram.
    """

    tokens: list[Token]
    ast: ASTNode | None
    errors: list[SyntaxErrorInfo]


class ParserError(Exception):
    """Erro de análise passível de recuperação.

    Attributes:
        info: Dados do erro para o relatório final.
    """

    def __init__(self, info: SyntaxErrorInfo):
        """Inicializa a exceção com os dados do erro.

        Args:
            info: Descrição e localização do erro.
        """
        self.info = info
        super().__init__(info.message)


class _AbortParsing(Exception):
    """Encerra a análise por completo, sem tentar recuperação.

    Usada quando insistir apenas geraria repetições do mesmo erro.
    """


class Parser:
    """Parser descendente recursivo com um token de lookahead.

    Ao encontrar um erro, aplica recuperação em modo pânico: registra o erro,
    descarta tokens até um ponto de sincronização e retoma a análise. Assim um
    único arquivo pode reportar vários erros em uma só execução.

    Attributes:
        tokens: Tokens recebidos do lexer.
        current: Índice do token de lookahead.
        errors: Erros registrados até o momento.
    """

    def __init__(self, tokens: list[Token]):
        """Posiciona o parser no primeiro token.

        Args:
            tokens: Tokens produzidos pelo lexer, encerrados por um token EOF.
        """
        self.tokens = tokens
        self.current = 0
        self.errors: list[SyntaxErrorInfo] = []
        self._depth = 0

    def node(self, kind, value=None, children=None, token=None):
        t = token or self._peek()
        return ASTNode(kind, value, children or [], t.line, t.column)

    def at(self, text): return self._peek().lexeme == text

    def take(self, text):
        if not self.at(text): self._error(self._peek(), repr(text))
        return self._advance()

    def parse(self):
        root = self.node('PROGRAMA')
        try:
            try:
                self.take('robot')
                name = self._consume(TokenType.IDENTIFICADOR, 'nome do robô')
                root.valor = name.lexeme
                root.filhos = [self.block()]
                self._consume(TokenType.EOF, 'fim do arquivo após o robô')
            except ParserError as error: self._record(error)
        except (_AbortParsing, RecursionError):
            if not self.errors:
                self.errors.append(SyntaxErrorInfo('Erro sintático: aninhamento excessivo', self._peek().line, self._peek().column, ''))
        return root, self.errors

    def block(self):
        with self._nesting(self._peek()):
            opening = self.take('{')
            commands = []
            while not self.at('}') and not self._check(TokenType.EOF):
                start = self.current
                try: commands.append(self.command())
                except ParserError as error:
                    self._record(error)
                    # Modo pânico: preserve o fechamento do bloco e garanta avanço.
                    while not self._check(TokenType.EOF) and not self.at('}'):
                        if self._advance().lexeme == ';': break
                    if self.current == start and not self.at('}'): self._advance()
            self.take('}')
            return self.node('BLOCO', children=commands, token=opening)

    def command(self):
        t = self._peek()
        if self.at('{'): return self.block()
        if t.lexeme in ('if', 'while'):
            with self._nesting(t):
                self._advance(); self.take('(')
                cond = self.expression(); self.take(')')
                children = [cond, self.block()]
                if t.lexeme == 'if' and self.at('else'):
                    self._advance()
                    children.append(self.command() if self.at('if') else self.block())
                return self.node(t.lexeme.upper(), children=children, token=t)
        if t.lexeme in ('break', 'continue'):
            self._advance(); self.take(';')
            return self.node(t.lexeme.upper(), token=t)
        if t.lexeme in ('const','int','float','bool','string'):
            const = self.at('const')
            if const: self._advance()
            typ = self._advance()
            if typ.lexeme not in ('int','float','bool','string'): self._error(typ, 'tipo')
            name = self._consume(TokenType.IDENTIFICADOR, 'identificador da declaração')
            children = []
            if self.at('='):
                self._advance(); children = [self.expression()]
            elif const: self._error(self._peek(), 'inicializador de constante')
            self.take(';')
            n = self.node('DECL', name.lexeme, children, t)
            n.meta = {'decl_type': typ.lexeme, 'const': const}
            return n
        name = self._consume(TokenType.IDENTIFICADOR, 'declaração, bloco ou comando')
        if self.at('('):
            self._advance(); args = []
            if not self.at(')'):
                args.append(self.expression())
                while self.at(','):
                    self._advance(); args.append(self.expression())
            self.take(')'); self.take(';')
            return self.node('CALL', name.lexeme, args, name)
        target = self.node('IDENTIFICADOR', name.lexeme, token=name)
        if self.at('.'):
            self._advance()
            target.valor += '.' + self._consume(TokenType.IDENTIFICADOR, 'campo').lexeme
        op = self._advance()
        if op.lexeme not in ('=','+=','-=','*=','/='): self._error(op, 'operador de atribuição')
        value = self.expression(); self.take(';')
        return self.node('ATRIBUICAO', op.lexeme, [target, value], name)

    def expression(self):
        with self._nesting(self._peek()): return self.binary(0)

    LEVELS = [('||',), ('&&',), ('==','!='), ('<','<=','>','>='), ('+','-'), ('*','/','%')]

    def binary(self, level):
        if level == len(self.LEVELS): return self.factor()
        node = self.binary(level+1)
        count = 0
        while self._peek().lexeme in self.LEVELS[level]:
            if level in (2,3) and count: self._error(self._peek(), 'comparação única; use parênteses ou &&')
            op = self._advance(); right = self.binary(level+1)
            node = self.node('BIN', op.lexeme, [node,right], op)
            count += 1
        return node

    def factor(self):
        t = self._peek()
        if t.lexeme in ('!','-','+'):
            with self._nesting(t):
                self._advance()
                return self.node('UNARY', t.lexeme, [self.factor()], t)
        if t.type in (TokenType.NUM_INTEIRO,TokenType.NUM_FLOAT,TokenType.CADEIA) or t.lexeme in ('true','false'):
            self._advance()
            val = (t.lexeme == 'true') if t.lexeme in ('true','false') else t.value
            return self.node('LITERAL', val, token=t)
        if t.type is TokenType.IDENTIFICADOR:
            self._advance(); name = t.lexeme
            if self.at('.'):
                self._advance(); name += '.' + self._consume(TokenType.IDENTIFICADOR, 'campo do sensor').lexeme
            return self.node('IDENTIFICADOR', name, token=t)
        if self.at('('):
            self._advance(); expr = self.expression(); self.take(')'); return expr
        self._error(t, 'literal, identificador ou expressão')

    @contextmanager
    def _nesting(self, token: Token) -> Iterator[None]:
        """Contabiliza um nível de aninhamento e barra recursão excessiva.

        O decremento fica em finally porque o erro é capturado pela recuperação
        em modo pânico e a análise continua depois dele.

        Args:
            token: Token usado para localizar um eventual erro de profundidade.

        Yields:
            None: Apenas delimita o trecho contabilizado.

        Raises:
            _AbortParsing: Se a profundidade exceder MAX_NESTING_DEPTH.
        """
        self._depth += 1
        try:
            if self._depth > MAX_NESTING_DEPTH:
                self._fail_depth(token)
            yield
        finally:
            self._depth -= 1

    def _synchronize(self, stop_at_block_end: bool) -> None:
        """Descarta tokens até um ponto seguro para retomar a análise.

        Consome sempre ao menos um token, o que garante progresso e evita laço
        infinito no chamador. A análise retoma logo após um ";", em um novo "if"
        ou, quando há um bloco aberto, no "}" que o fecha.

        Args:
            stop_at_block_end: Interrompe o descarte no "}" de um bloco aberto.
        """
        self._advance()

        while not self._check(TokenType.EOF):
            if self._previous().type is TokenType.PONTO_VIRGULA:
                return
            if stop_at_block_end and self._check(TokenType.FECHA_CHAVE):
                return
            if self._is_reserved("if"):
                return
            self._advance()

    def _peek(self) -> Token:
        """Consulta o token de lookahead sem consumi-lo."""
        return self.tokens[self.current]

    def _previous(self) -> Token:
        """Consulta o último token consumido."""
        return self.tokens[self.current - 1]

    def _advance(self) -> Token:
        """Consome o token de lookahead, sem passar do token EOF.

        Returns:
            O token consumido.
        """
        token = self._peek()
        if token.type is not TokenType.EOF:
            self.current += 1
        return token

    def _check(self, token_type: TokenType) -> bool:
        """Verifica o tipo do token de lookahead.

        Args:
            token_type: Tipo esperado na posição atual.

        Returns:
            True se o token de lookahead for desse tipo.
        """
        return self._peek().type is token_type

    def _match(self, *token_types: TokenType) -> bool:
        """Consome o token de lookahead se ele for de um dos tipos informados.

        Args:
            *token_types: Tipos aceitos na posição atual.

        Returns:
            True se um token foi consumido.
        """
        if self._peek().type in token_types:
            self._advance()
            return True
        return False

    def _consume(self, token_type: TokenType, expected: str) -> Token:
        """Exige um token do tipo informado na posição atual.

        Args:
            token_type: Tipo obrigatório na posição atual.
            expected: Descrição do símbolo esperado, usada na mensagem de erro.

        Returns:
            O token consumido.

        Raises:
            ParserError: Se o token de lookahead for de outro tipo.
        """
        if self._check(token_type):
            return self._advance()
        self._error(self._peek(), expected)

    def _is_reserved(self, word: str) -> bool:
        """Verifica se o token de lookahead é uma palavra reservada específica.

        Args:
            word: Lexema esperado na posição atual.

        Returns:
            True se o token de lookahead for essa palavra reservada.
        """
        token = self._peek()
        return token.type is TokenType.PALAVRA_RESERVADA and token.lexeme == word

    def _consume_reserved(self, word: str) -> Token:
        """Exige uma palavra reservada específica na posição atual.

        Args:
            word: Lexema obrigatório na posição atual.

        Returns:
            O token consumido.

        Raises:
            ParserError: Se o token de lookahead não for essa palavra.
        """
        if self._is_reserved(word):
            return self._advance()
        self._error(self._peek(), f"'{word}'")

    @staticmethod
    def _error(token: Token, expected: str) -> NoReturn:
        """Reporta o token informado como inválido.

        Um token ERRO produzido pelo lexer é sempre reportado como erro léxico,
        mesmo quando aparece onde o parser esperava um símbolo específico.
        Qualquer outro token inesperado é erro sintático.

        Args:
            token: Token que interrompeu a análise.
            expected: Descrição do símbolo esperado na posição.

        Raises:
            ParserError: Sempre.
        """
        found = token.lexeme if token.lexeme else "EOF"

        if token.type is TokenType.ERRO:
            message = f"Erro lexico: token invalido '{found}'."
        else:
            message = f"Erro sintático: esperado {expected}, encontrado '{found}'."

        raise ParserError(SyntaxErrorInfo(message, token.line, token.column, found))

    def _record(self, error: ParserError) -> None:
        """Registra um erro recuperável e aplica o teto de erros.

        Args:
            error: Erro capturado pela recuperação em modo pânico.

        Raises:
            _AbortParsing: Se MAX_REPORTED_ERRORS for atingido.
        """
        self.errors.append(error.info)
        if len(self.errors) >= MAX_REPORTED_ERRORS:
            raise _AbortParsing

    def _fail_depth(self, token: Token) -> NoReturn:
        """Registra o estouro de aninhamento e encerra a análise.

        Ao contrário dos demais erros, este não é recuperável: retomar dentro de
        uma estrutura profunda demais reproduziria o mesmo erro a cada nível
        restante, poluindo o relatório.

        Args:
            token: Token usado para localizar o erro.

        Raises:
            _AbortParsing: Sempre.
        """
        found = token.lexeme if token.lexeme else "EOF"
        message = (
            f"Erro sintático: aninhamento excede o limite de "
            f"{MAX_NESTING_DEPTH} niveis."
        )
        self.errors.append(SyntaxErrorInfo(message, token.line, token.column, found))
        raise _AbortParsing


def format_ast(node: ASTNode, prefix: str = "", is_last: bool = True) -> str:
    """Formata a árvore em texto, com conectores de indentação.

    Args:
        node: Nó raiz do trecho a ser formatado.
        prefix: Indentação acumulada dos níveis anteriores.
        is_last: Indica que o nó é o último filho do seu pai.

    Returns:
        A árvore formatada, um nó por linha.
    """
    connector = "└── " if is_last else "├── "
    label = node.tipo
    if node.valor is not None:
        label += f" [{node.valor}]"

    lines = [prefix + connector + label]
    child_prefix = prefix + ("    " if is_last else "│   ")

    for index, child in enumerate(node.filhos):
        lines.append(format_ast(child, child_prefix, index == len(node.filhos) - 1))

    return "\n".join(lines)


def format_errors(errors: list[SyntaxErrorInfo]) -> str:
    """Formata a lista de erros para exibição.

    Uma nota final indica que a análise foi interrompida quando o teto de erros
    é atingido, situação em que _record aborta imediatamente.

    Args:
        errors: Erros registrados pelo parser.

    Returns:
        O total de erros seguido de uma linha por erro, com linha e coluna.
    """
    lines = [f"Total de erros: {len(errors)}", ""]
    lines.extend(
        f"{index}. Linha {error.line}, coluna {error.column}: {error.message}"
        for index, error in enumerate(errors, start=1)
    )

    if len(errors) >= MAX_REPORTED_ERRORS:
        lines += ["", f"Análise interrompida ao atingir {MAX_REPORTED_ERRORS} erros."]

    return "\n".join(lines)


def analyze_source(source: str) -> AnalysisResult:
    """Executa as duas fases da análise sobre um código-fonte.

    Args:
        source: Código-fonte completo a ser analisado.

    Returns:
        Os tokens, a árvore sintática e os erros encontrados. A árvore é None
        quando há erros.
    """
    tokens = Lexer(source).tokenize()
    ast, errors = Parser(tokens).parse()
    return AnalysisResult(tokens, None if errors else ast, errors)


def write_json(ast: ASTNode, output: Path) -> None:
    """Grava a árvore sintática em um arquivo JSON.

    Args:
        ast: Árvore a ser serializada.
        output: Caminho do arquivo de saída.
    """
    output.write_text(
        json.dumps(ast.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_file(
    path: Path,
    show_tokens: bool = True,
    ast_json: Path | None = None,
) -> int:
    """Analisa um arquivo e imprime o relatório da análise.

    Args:
        path: Arquivo com o código-fonte.
        show_tokens: Inclui a tabela de tokens no relatório.
        ast_json: Caminho para salvar a árvore em JSON, usado apenas quando a
            análise não encontra erros.

    Returns:
        0 se o código-fonte for válido, 1 se houver erros.
    """
    result = analyze_source(path.read_text(encoding="utf-8"))

    print(f"=== ARQUIVO: {path.name} ===")

    if show_tokens:
        print("\n--- TABELA DE TOKENS ---")
        print(render_token_table(result.tokens))

    print("\n--- RESULTADO ---")

    if result.errors:
        print("INVÁLIDO\n")
        print(format_errors(result.errors))
        return 1

    assert result.ast is not None
    print("VÁLIDO")
    print("\n--- ÁRVORE SINTÁTICA ABSTRATA (AST) ---")
    print(format_ast(result.ast))

    if ast_json is not None:
        write_json(result.ast, ast_json)
        print(f"\nAST salva em: {ast_json}")

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Monta o interpretador de argumentos da linha de comando.

    Returns:
        O interpretador configurado com o arquivo de entrada e as opções.
    """
    parser = argparse.ArgumentParser(
        description="Parser descendente recursivo do trabalho de compiladores."
    )
    parser.add_argument("arquivo", help="arquivo .txt com o código-fonte")
    parser.add_argument(
        "--sem-tokens",
        action="store_true",
        help="não exibe a tabela de tokens",
    )
    parser.add_argument(
        "--ast-json",
        type=Path,
        help="salva a AST válida em JSON no caminho informado",
    )
    return parser


def main() -> int:
    """Executa a análise sobre o arquivo indicado na linha de comando.

    Returns:
        0 se o código-fonte for válido, 1 se houver erros e 2 se o arquivo não
        existir.
    """
    args = build_arg_parser().parse_args()
    path = Path(args.arquivo)

    if not path.exists():
        print(f"Arquivo não encontrado: {path}")
        return 2

    return run_file(path, show_tokens=not args.sem_tokens, ast_json=args.ast_json)


if __name__ == "__main__":
    raise SystemExit(main())
