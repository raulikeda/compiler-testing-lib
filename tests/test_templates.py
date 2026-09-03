"""Legacy single-file command templates are rewritten to multi-file forms."""
from compiler_testing_lib import runner


def test_go_legacy_template_is_rewritten():
    assert runner.normalize_command_template("go run main.go") == "go run ."


def test_whitespace_insensitive():
    assert runner.normalize_command_template("  go   run main.go ") == "go run ."


def test_other_templates_untouched():
    for template in ["python3 main.py", "node main.js", "java main.java",
                     "g++ main.cpp -o main && ./main", "go run ."]:
        assert runner.normalize_command_template(template) == template


def test_is_go_template():
    assert runner.is_go_template("go run main.go")
    assert runner.is_go_template("go run .")
    assert not runner.is_go_template("python3 main.py")
    assert not runner.is_go_template("cargo run --release --")


def test_go_module_hint_only_for_nested_sources_without_go_mod(tmp_path):
    (tmp_path / "main.go").write_text("package main\n")
    assert runner.go_module_hint(tmp_path) is None

    (tmp_path / "lexer").mkdir()
    (tmp_path / "lexer" / "lexer.go").write_text("package lexer\n")
    hint = runner.go_module_hint(tmp_path)
    assert hint and "go mod init" in hint

    (tmp_path / "go.mod").write_text("module compiler\n\ngo 1.24\n")
    assert runner.go_module_hint(tmp_path) is None


def test_go_module_hint_ignores_git_dir(tmp_path):
    (tmp_path / ".git" / "x").mkdir(parents=True)
    (tmp_path / ".git" / "x" / "hook.go").write_text("")
    assert runner.go_module_hint(tmp_path) is None


def test_python_entry_file():
    assert runner.python_entry_file("python3 main.py") == "main.py"
    assert runner.python_entry_file("python src/main.py") == "src/main.py"
    assert runner.python_entry_file("python3 -u compiler.py") == "compiler.py"
    assert runner.python_entry_file("python3") == "main.py"
