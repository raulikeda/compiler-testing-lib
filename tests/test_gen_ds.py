"""The three rewrites gen_ds.to_iso_ebnf applies to turn a course key into
ISO-14977 for DrawGrammar; every other construct must pass through untouched."""
import glob, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from gen_ds import to_iso_ebnf  # noqa: E402

SYNTAX = os.path.join(os.path.dirname(__file__), "..", "compiler_testing_lib", "syntax")
BARE = r"(?<![\w\"'.])(?:[0-9]|[A-Za-z]|\.\.\.)(?![\w\"'.])"


def test_epsilon_becomes_empty_alternative():
    assert to_iso_ebnf('X = ("a" | ε) ;') == 'X = ("a" | ) ;'
    assert to_iso_ebnf('X = (λ | "a") ;') == 'X = ( | "a") ;'


def test_bare_digits_letters_and_ellipsis_get_quoted():
    assert to_iso_ebnf("DIGIT = 0 | 1 | ... | 9 ;") == 'DIGIT = "0" | "1" | "..." | "9" ;'
    assert to_iso_ebnf("LETTER = a | b | ... | z | A | B | ... | Z ;") == \
        'LETTER = "a" | "b" | "..." | "z" | "A" | "B" | "..." | "Z" ;'


def test_line_comments_become_iso_comments():
    assert to_iso_ebnf('X = "a" ; // note\n') == 'X = "a" ; (* note *)\n'


def test_everything_else_is_untouched():
    src = 'BLOCK = "{", "\\n", { STATEMENT }, "}" ;\nS = \'"\', { LETTER | DIGIT | " " }, \'"\' ;\n'
    assert to_iso_ebnf(src) == src


def test_every_key_in_the_repo_converts_without_leftovers():
    keys = glob.glob(os.path.join(SYNTAX, "*", "ebnf-*.txt"))
    assert keys
    for key in keys:
        iso = to_iso_ebnf(open(key).read())
        assert "ε" not in iso and "//" not in iso, key
        assert not re.search(BARE, iso), key
