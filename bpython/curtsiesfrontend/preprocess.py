"""Tools for preparing code to be run in the REPL (removing blank lines,
etc)"""

from codeop import CommandCompiler
from re import Match
from itertools import tee, islice, chain

from ..lazyre import LazyReCompile

# TODO specifically catch IndentationErrors instead of any syntax errors

indent_empty_lines_re = LazyReCompile(r"\s*")
tabs_to_spaces_re = LazyReCompile(r"^\t+")

# keywords introducing a clause that continues the block above it rather than
# starting a new statement, even though they sit at the same indentation
BLOCK_CONTINUATION_CLAUSES = frozenset(("elif", "else", "except", "finally"))


def indent_empty_lines(s: str, compiler: CommandCompiler) -> str:
    """Indents blank lines that would otherwise cause early compilation

    Only really works if starting on a new line"""
    initial_lines = s.split("\n")
    ends_with_newline = False
    if initial_lines and not initial_lines[-1]:
        ends_with_newline = True
        initial_lines.pop()
    result_lines = []

    prevs, lines, nexts = tee(initial_lines, 3)
    prevs = chain(("",), prevs)
    nexts = chain(islice(nexts, 1, None), ("",))

    for p_line, line, n_line in zip(prevs, lines, nexts):
        if len(line) == 0:
            # "\s*" always matches
            p_indent = indent_empty_lines_re.match(p_line).group()  # type: ignore
            n_indent = indent_empty_lines_re.match(n_line).group()  # type: ignore
            result_lines.append(min([p_indent, n_indent], key=len) + line)
        else:
            result_lines.append(line)

    return "\n".join(result_lines) + ("\n" if ends_with_newline else "")


def leading_tabs_to_spaces(s: str) -> str:
    def tab_to_space(m: Match[str]) -> str:
        return len(m.group()) * 4 * " "

    return "\n".join(
        tabs_to_spaces_re.sub(tab_to_space, line) for line in s.split("\n")
    )


def _compiles(lines: list[str], compiler: CommandCompiler) -> bool:
    try:
        return bool(compiler("\n".join(lines)))
    except (ValueError, SyntaxError, OverflowError):
        return False


def starts_new_statement(line: str) -> bool:
    """Whether a line is a statement of its own rather than part of a block"""
    if not line.strip() or line[:1].isspace():
        return False
    # a comment is inert, and may well be sitting above an 'else:'
    if line.startswith("#"):
        return False
    return (
        line.split(maxsplit=1)[0].rstrip(":") not in BLOCK_CONTINUATION_CLAUSES
    )


def separate_blocks(s: str, compiler: CommandCompiler) -> str:
    """Insert the blank lines needed to close indented blocks

    Interactively a block is ended by a blank line, but pasted code has none
    between a block and the statement that follows it, so without this that
    statement would be swallowed into the block instead of being run.

    Only really works if starting on a new line"""
    result_lines: list[str] = []
    # the lines the REPL would currently be holding in its buffer
    buffer: list[str] = []

    for line in s.split("\n"):
        # A block is merely waiting for its blank line, whereas a buffer held
        # open by an unclosed bracket stays unfinished however many follow.
        if (
            buffer
            and starts_new_statement(line)
            and _compiles(buffer + ["", ""], compiler)
        ):
            result_lines.append("")
            buffer = []

        result_lines.append(line)
        buffer.append(line)
        if not line.strip() or _compiles(buffer, compiler):
            # the REPL runs the buffer and starts collecting afresh
            buffer = []

    return "\n".join(result_lines)


def preprocess(s: str, compiler: CommandCompiler) -> str:
    return separate_blocks(
        indent_empty_lines(leading_tabs_to_spaces(s), compiler), compiler
    )
