"""Analisador léxico

Converte o código-fonte em uma lista de tokens, cada um com tipo, lexema, valor,
linha e coluna. A classificação é feita por uma máquina de estados implementada
diretamente em Python, sem expressões regulares.
"""

from __future__ import annotations

import sys
import math
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class TokenType(Enum):
    """Conjunto fechado de tipos de tokens reconhecidos pelo analisador léxico.

    ERRO identifica um lexema inválido e EOF marca o fim do código-fonte.
    """

    PALAVRA_RESERVADA = auto()
    IDENTIFICADOR = auto()
    NUM_INTEIRO = auto()
    CADEIA = auto()
    NUM_FLOAT = auto()
    OPERADOR = auto()
    DELIMITADOR = auto()

    OP_SOMA = auto()
    OP_SUBTRACAO = auto()
    OP_MULTIPLICACAO = auto()
    OP_DIVISAO = auto()
    ATRIBUICAO = auto()

    OP_IGUAL = auto()
    OP_DIFERENTE = auto()
    OP_MENOR = auto()
    OP_MENOR_IGUAL = auto()
    OP_MAIOR = auto()
    OP_MAIOR_IGUAL = auto()

    ABRE_PAREN = auto()
    FECHA_PAREN = auto()
    ABRE_CHAVE = auto()
    FECHA_CHAVE = auto()
    PONTO_VIRGULA = auto()

    ERRO = auto()
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    """Unidade léxica produzida pelo lexer.

    Attributes:
        type: Categoria do token.
        lexeme: Trecho do código-fonte que originou o token.
        value: Valor convertido do lexema. Inteiro para NUM_INTEIRO, texto sem
            as aspas e com escapes resolvidos para CADEIA, None para operadores
            e delimitadores.
        line: Linha em que o lexema começa, contada a partir de 1.
        column: Coluna em que o lexema começa, contada a partir de 1.
    """

    type: TokenType
    lexeme: str
    value: int | float | str | None
    line: int
    column: int


RESERVED_WORDS: dict[str, TokenType] = {
    "int": TokenType.PALAVRA_RESERVADA,
    "if": TokenType.PALAVRA_RESERVADA,
    **{w: TokenType.PALAVRA_RESERVADA for w in "robot const float bool string true false else while break continue".split()},
}
"""Lexemas que deixam de ser IDENTIFICADOR e passam a ser PALAVRA_RESERVADA.

Palavras de RoboLang, incluindo tipos e controle de fluxo.
"""

SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    "+": TokenType.OP_SOMA,
    "-": TokenType.OP_SUBTRACAO,
    "*": TokenType.OP_MULTIPLICACAO,
    "/": TokenType.OP_DIVISAO,
    "(": TokenType.ABRE_PAREN,
    ")": TokenType.FECHA_PAREN,
    "{": TokenType.ABRE_CHAVE,
    "}": TokenType.FECHA_CHAVE,
    ";": TokenType.PONTO_VIRGULA,
}
"""Símbolos cujo tipo é determinado por um único caractere."""

COMPARISON_STARTERS = frozenset("=!<>")
"""Caracteres que iniciam um operador de uma ou de duas posições.

O tipo depende do caractere seguinte, portanto ficam fora de SINGLE_CHAR_TOKENS
e são resolvidos em Lexer._scan_comparison_or_assignment.
"""

ESCAPE_SEQUENCES: dict[str, str] = {
    '"': '"',
    "\\": "\\",
    "n": "\n",
    "t": "\t",
}
"""Traduções aplicadas ao caractere que segue uma barra invertida em uma cadeia.

Qualquer escape ausente deste mapa produz um token ERRO.
"""

WHITESPACE_CHARACTERS = frozenset(" \t\r\n")
"""Caracteres descartados entre tokens."""


class Lexer:
    """Percorre o código-fonte caractere a caractere e produz tokens.

    A instância mantém o cursor da análise, portanto serve para um único
    código-fonte.
    """

    def __init__(self, source: str) -> None:
        """Posiciona o cursor no primeiro caractere do código-fonte.

        Args:
            source: Código-fonte completo a ser analisado.
        """
        self._source = source
        self._position = 0
        self._line = 1
        self._column = 1

    def tokenize(self) -> list[Token]:
        """Analisa o código-fonte inteiro.

        Returns:
            Todos os tokens do código-fonte, sempre encerrados por um token EOF.
            Lexemas inválidos aparecem como tokens de tipo ERRO, sem interromper
            a análise.
        """
        tokens: list[Token] = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.type is TokenType.EOF:
                return tokens

    def next_token(self) -> Token:
        """Produz o próximo token, descartando os espaços que o antecedem.

        O primeiro caractere do lexema determina qual scanner é chamado, o que
        dispensa retroceder o cursor.

        Returns:
            O token iniciado na posição atual, ou um token EOF se o código-fonte
            terminou.
        """
        while True:
            self._skip_whitespace()
            start, line, col = self._position, self._line, self._column
            if self._source.startswith('//', start):
                while not self._is_at_end() and self._peek() not in ('\n', '\r'):
                    self._advance()
                continue
            if self._source.startswith('/*', start):
                self._advance(); self._advance()
                while not self._is_at_end() and not self._source.startswith('*/', self._position):
                    self._advance()
                if self._is_at_end():
                    return Token(TokenType.ERRO, self._source[start:], 'comentário não terminado', line, col)
                self._advance(); self._advance()
                continue
            break
        if self._is_at_end():
            return Token(TokenType.EOF, "", None, line, col)
        ch = self._peek()
        if self._is_identifier_start(ch): return self._scan_identifier()
        if self._is_digit(ch): return self._scan_number()
        if ch == '"': return self._scan_string()
        pair = self._source[self._position:self._position+2]
        if pair in ('++', '--'):
            self._advance(); self._advance()
            return Token(TokenType.ERRO, pair, 'operador não implementado', line, col)
        if pair in ('==','!=','<=','>=','&&','||','+=','-=','*=','/='):
            self._advance(); self._advance()
            return Token(TokenType.OPERADOR, pair, None, line, col)
        if ch in '=!<>%':
            self._advance()
            return Token(TokenType.OPERADOR, ch, None, line, col)
        if ch in '.,':
            self._advance()
            return Token(TokenType.DELIMITADOR, ch, None, line, col)
        if ch in SINGLE_CHAR_TOKENS: return self._scan_single_char_token()
        return self._scan_unknown()

    def _is_at_end(self) -> bool:
        """Indica se o cursor passou do último caractere do código-fonte."""
        return self._position >= len(self._source)

    def _peek(self) -> str:
        """Consulta o caractere atual sem consumi-lo.

        Returns:
            O caractere na posição do cursor, ou uma string vazia no fim do
            código-fonte.
        """
        if self._is_at_end():
            return ""
        return self._source[self._position]

    def _advance(self) -> str:
        """Consome o caractere atual e atualiza linha e coluna.

        A sequência CRLF é consumida por inteiro e contada como uma única quebra
        de linha.

        Returns:
            O caractere consumido.
        """
        index = self._position
        character = self._source[index]
        self._position += 1

        if character == "\r":
            if self._position < len(self._source) and self._source[self._position] == "\n":
                self._position += 1
            self._line += 1
            self._column = 1
        elif character == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1

        return character

    def _skip_whitespace(self) -> None:
        """Avança o cursor sobre espaços, tabulações e quebras de linha."""
        while self._peek() in WHITESPACE_CHARACTERS:
            self._advance()

    def _scan_identifier(self) -> Token:
        """Lê um identificador ou uma palavra reservada.

        O lexema é lido por inteiro e só então comparado com RESERVED_WORDS, o
        que dispensa retroceder o cursor em casos como "iforme".

        Returns:
            Um token PALAVRA_RESERVADA se o lexema constar em RESERVED_WORDS, ou
            um token IDENTIFICADOR caso contrário.
        """
        start_position = self._position
        start_line = self._line
        start_column = self._column

        while self._is_identifier_part(self._peek()):
            self._advance()

        lexeme = self._source[start_position:self._position]
        token_type = RESERVED_WORDS.get(lexeme, TokenType.IDENTIFICADOR)
        return Token(token_type, lexeme, lexeme, start_line, start_column)

    def _scan_number(self) -> Token:
        """Lê uma sequência de dígitos.

        Dígitos seguidos de letra ou de sublinhado formam um único lexema
        malformado, de modo que "12abc" produz um token ERRO em vez de um número
        seguido de um identificador.

        Returns:
            Um token NUM_INTEIRO com o valor convertido para int, ou um token
            ERRO se o lexema for malformado.
        """
        start_position = self._position
        start_line = self._line
        start_column = self._column

        while self._is_digit(self._peek()):
            self._advance()

        floating = False
        if self._peek() == '.' and self._position+1 < len(self._source) and self._is_digit(self._source[self._position+1]):
            floating = True
            self._advance()
            while self._is_digit(self._peek()): self._advance()
        if self._is_identifier_start(self._peek()):
            while self._is_identifier_part(self._peek()):
                self._advance()
            lexeme = self._source[start_position:self._position]
            return Token(TokenType.ERRO, lexeme, None, start_line, start_column)

        lexeme = self._source[start_position:self._position]
        try:
            value = float(lexeme) if floating else int(lexeme)
        except ValueError:
            return Token(TokenType.ERRO, lexeme, 'número excede limite', start_line, start_column)
        if floating and not math.isfinite(value):
            return Token(TokenType.ERRO, lexeme, 'float não finito', start_line, start_column)
        return Token(TokenType.NUM_FLOAT if floating else TokenType.NUM_INTEIRO, lexeme, value, start_line, start_column)

    def _scan_comparison_or_assignment(self) -> Token:
        """Lê um operador iniciado por um caractere de COMPARISON_STARTERS.

        Cada caractere decide entre a forma de uma posição e a de duas
        consultando o caractere seguinte, sempre preferindo o lexema mais longo.
        O último ramo trata ">", único caractere restante. O caractere "!"
        isolado não pertence à linguagem, que não possui negação lógica.

        Returns:
            O token do operador lido, ou um token ERRO para um "!" isolado.
        """
        start_line = self._line
        start_column = self._column
        character = self._advance()

        if character == "=":
            if self._peek() == "=":
                self._advance()
                return Token(TokenType.OP_IGUAL, "==", None, start_line, start_column)
            return Token(TokenType.ATRIBUICAO, "=", None, start_line, start_column)

        if character == "!":
            if self._peek() == "=":
                self._advance()
                return Token(TokenType.OP_DIFERENTE, "!=", None, start_line, start_column)
            return Token(TokenType.ERRO, "!", None, start_line, start_column)

        if character == "<":
            if self._peek() == "=":
                self._advance()
                return Token(TokenType.OP_MENOR_IGUAL, "<=", None, start_line, start_column)
            return Token(TokenType.OP_MENOR, "<", None, start_line, start_column)

        if self._peek() == "=":
            self._advance()
            return Token(TokenType.OP_MAIOR_IGUAL, ">=", None, start_line, start_column)
        return Token(TokenType.OP_MAIOR, ">", None, start_line, start_column)

    def _scan_string(self) -> Token:
        """Lê uma cadeia delimitada por aspas duplas.

        A aspa de abertura é consumida antes do laço de leitura e as sequências
        de ESCAPE_SEQUENCES são resolvidas no valor do token. Uma cadeia
        interrompida por quebra de linha ou por fim de arquivo é um erro léxico,
        e o lexema devolvido vai até o ponto da interrupção para indicar onde
        falta a aspa de fechamento.

        Returns:
            Um token CADEIA cujo lexema inclui as aspas e cujo valor as exclui,
            ou um token ERRO se a cadeia não for fechada.
        """
        start_position = self._position
        start_line = self._line
        start_column = self._column

        self._advance()
        value_characters: list[str] = []
        invalid = False

        while True:
            if self._is_at_end() or self._peek() in ("\n", "\r"):
                lexeme = self._source[start_position:self._position]
                return Token(TokenType.ERRO, lexeme, None, start_line, start_column)

            character = self._advance()

            if character == '"':
                lexeme = self._source[start_position:self._position]
                value = "".join(value_characters)
                return Token(TokenType.ERRO if invalid else TokenType.CADEIA, lexeme, "escape desconhecido" if invalid else value, start_line, start_column)

            if character == "\\" and not self._is_at_end():
                if self._peek() in ('\n', '\r'):
                    return Token(TokenType.ERRO, self._source[start_position:self._position], 'quebra de linha na string', start_line, start_column)
                escaped = self._advance()
                invalid |= escaped not in ESCAPE_SEQUENCES
                value_characters.append(ESCAPE_SEQUENCES.get(escaped, escaped))
                continue

            value_characters.append(character)

    def _scan_single_char_token(self) -> Token:
        """Lê um símbolo de SINGLE_CHAR_TOKENS.

        Returns:
            O token correspondente ao caractere consumido.
        """
        start_line = self._line
        start_column = self._column
        character = self._advance()
        return Token(
            SINGLE_CHAR_TOKENS[character],
            character,
            None,
            start_line,
            start_column,
        )

    def _scan_unknown(self) -> Token:
        """Consome um caractere que nenhum scanner reconhece.

        Returns:
            Um token ERRO com o caractere consumido como lexema.
        """
        start_line = self._line
        start_column = self._column
        character = self._advance()
        return Token(TokenType.ERRO, character, None, start_line, start_column)

    @staticmethod
    def _is_identifier_start(character: str) -> bool:
        """Indica se o caractere pode iniciar um identificador."""
        return "a" <= character <= "z" or "A" <= character <= "Z" or character == "_"

    @staticmethod
    def _is_digit(character: str) -> bool:
        """Indica se o caractere é um dígito decimal."""
        return "0" <= character <= "9"

    @staticmethod
    def _is_identifier_part(character: str) -> bool:
        """Indica se o caractere pode continuar um identificador.

        Difere de _is_identifier_start por aceitar dígitos, o que torna "x1" um
        identificador válido e "1x" um lexema malformado.
        """
        return Lexer._is_identifier_start(character) or Lexer._is_digit(character)


def _format_cell(value: object) -> str:
    """Formata um campo de token para exibição na tabela.

    Args:
        value: Campo do token a ser exibido.

    Returns:
        A representação textual do campo, ou "-" se ele for None ou vazio.
    """
    return "-" if value is None or value == "" else str(value)


def render_token_table(tokens: list[Token]) -> str:
    """Monta a tabela de tokens em texto, com as colunas alinhadas.

    A largura de cada coluna acompanha o maior valor nela. As colunas de índice,
    linha e coluna são alinhadas à direita.

    Args:
        tokens: Tokens a serem exibidos, na ordem de leitura.

    Returns:
        A tabela formatada, seguida do total de tokens e do total de erros
        léxicos.
    """
    headers = ["#", "TIPO", "LEXEMA", "VALOR", "LINHA", "COLUNA"]
    rows: list[list[str]] = []

    for index, token in enumerate(tokens, start=1):
        rows.append([
            str(index),
            token.type.name,
            _format_cell(token.lexeme),
            _format_cell(token.value),
            str(token.line),
            str(token.column),
        ])

    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    right_aligned = {0, 4, 5}

    def render_row(cells: list[str]) -> str:
        """Formata uma linha da tabela segundo as larguras calculadas.

        Args:
            cells: Valores da linha, na ordem das colunas.

        Returns:
            A linha formatada.
        """
        result: list[str] = []
        for i, cell in enumerate(cells):
            result.append(cell.rjust(widths[i]) if i in right_aligned else cell.ljust(widths[i]))
        return "  ".join(result)

    lines = [render_row(headers), "  ".join("-" * width for width in widths)]
    lines.extend(render_row(row) for row in rows)
    errors = sum(token.type is TokenType.ERRO for token in tokens)
    lines += ["", f"Total de tokens: {len(tokens)}", f"Erros lexicos: {errors}"]
    return "\n".join(lines)


def main() -> int:
    """Executa o analisador léxico sobre o arquivo indicado na linha de comando.

    Returns:
        0 se nenhum erro léxico for encontrado, 1 se houver erros léxicos e 2 se
        os argumentos estiverem incorretos.
    """
    if len(sys.argv) != 2:
        print("Uso: python lexer.py <arquivo>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).read_text(encoding="utf-8")
    tokens = Lexer(source).tokenize()
    print(render_token_table(tokens))
    return 1 if any(token.type is TokenType.ERRO for token in tokens) else 0


if __name__ == "__main__":
    raise SystemExit(main())
