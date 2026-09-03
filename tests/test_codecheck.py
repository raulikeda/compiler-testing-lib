"""codecheck must follow project-local imports across files and packages."""
import textwrap

import pytest

from compiler_testing_lib import codecheck


def write(root, files):
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
    return root / "main.py"


def class_names(modules):
    return {
        node.name
        for module in modules
        for node in codecheck.stdlib_ast.walk(module)
        if isinstance(node, codecheck.stdlib_ast.ClassDef)
    }


EXPECTED = {"Parser": ["run"], "Lexer": ["select_next"], "Token": []}

PACKAGE_LAYOUT = {
    "main.py": """
        import os, sys, yaml
        from src.parser import Parser

        if __name__ == "__main__":
            Parser.run(sys.argv[1])
    """,
    "src/parser.py": """
        from .lexer import Lexer
        from . import tokens
        from src import lexer

        class Parser:
            lexer = None

            @staticmethod
            def run(code):
                Parser.lexer = Lexer(code)
                return tokens.Token("INT", 1)
    """,
    "src/lexer.py": """
        from src import parser
        from .tokens import Token

        class Lexer:
            def __init__(self, source):
                self.source = source

            def select_next(self):
                return Token("EOF", None)
    """,
    "src/tokens.py": """
        class Token:
            def __init__(self, type, value):
                self.type = type
                self.value = value
    """,
}


def test_flat_layout(tmp_path):
    main = write(tmp_path, {
        "main.py": "import lexer\nfrom parser import Parser\n",
        "lexer.py": "class Lexer: pass\n",
        "parser.py": "from lexer import Lexer\nclass Parser: pass\n",
    })
    modules = codecheck.load_program_ast(main)
    assert len(modules) == 3
    assert class_names(modules) == {"Lexer", "Parser"}


def test_namespace_package_without_init(tmp_path):
    main = write(tmp_path, PACKAGE_LAYOUT)
    modules = codecheck.load_program_ast(main)
    assert class_names(modules) == {"Parser", "Lexer", "Token"}
    assert len(modules) == 4


def test_regular_package_with_init_is_included(tmp_path):
    layout = dict(PACKAGE_LAYOUT)
    layout["src/__init__.py"] = "class FromInit: pass\n"
    main = write(tmp_path, layout)
    modules = codecheck.load_program_ast(main)
    assert class_names(modules) == {"Parser", "Lexer", "Token", "FromInit"}


def test_import_dotted_module(tmp_path):
    main = write(tmp_path, {
        "main.py": "import src.tokens\nimport src.sub.deep\n",
        "src/tokens.py": "class Token: pass\n",
        "src/sub/deep.py": "class Deep: pass\n",
    })
    assert class_names(codecheck.load_program_ast(main)) == {"Token", "Deep"}


def test_from_package_import_submodule(tmp_path):
    main = write(tmp_path, {
        "main.py": "from src import lexer, parser\n",
        "src/lexer.py": "class Lexer: pass\n",
        "src/parser.py": "class Parser: pass\n",
    })
    assert class_names(codecheck.load_program_ast(main)) == {"Lexer", "Parser"}


def test_relative_import_of_package_itself_does_not_crash(tmp_path):
    main = write(tmp_path, {
        "main.py": "from src.a import A\n",
        "src/__init__.py": "",
        "src/a.py": "from . import b\nfrom .. import src\nclass A: pass\n",
        "src/b.py": "class B: pass\n",
    })
    assert class_names(codecheck.load_program_ast(main)) == {"A", "B"}


def test_entry_file_is_first_module(tmp_path):
    main = write(tmp_path, PACKAGE_LAYOUT)
    modules = codecheck.load_program_ast(main)
    assert class_names([modules[0]]) == set()


def test_stdlib_and_third_party_are_ignored(tmp_path):
    main = write(tmp_path, {"main.py": "import os\nimport json\nfrom pathlib import Path\n"})
    assert len(codecheck.load_program_ast(main)) == 1


def test_missing_local_module_is_skipped(tmp_path):
    main = write(tmp_path, {"main.py": "from src.nothing import X\nimport nowhere\n"})
    assert len(codecheck.load_program_ast(main)) == 1


def test_check_accepts_sub_package_layout(tmp_path):
    main = write(tmp_path, PACKAGE_LAYOUT)
    errors = codecheck.check(str(main), EXPECTED)
    assert errors == []


def test_check_still_reports_missing_class(tmp_path):
    layout = dict(PACKAGE_LAYOUT)
    layout["src/tokens.py"] = "class NotToken: pass\n"
    layout["src/lexer.py"] = layout["src/lexer.py"].replace("Token", "NotToken")
    layout["src/parser.py"] = layout["src/parser.py"].replace("tokens.Token", "tokens.NotToken")
    main = write(tmp_path, layout)
    errors = codecheck.check(str(main), EXPECTED)
    assert "Expected class `Token` not found" in errors
    assert "Unexpected class `NotToken` found" in errors


def test_check_relative_path_resolved_against_cwd(tmp_path, monkeypatch):
    write(tmp_path, PACKAGE_LAYOUT)
    monkeypatch.chdir(tmp_path)
    assert codecheck.check("main.py", EXPECTED) == []
