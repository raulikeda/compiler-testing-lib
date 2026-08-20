"""The command-line interface."""

import pytest

from compiler_testing_lib.transpiler.__main__ import main


def test_transpile_subcommand(tmp_path, capsys):
    src = tmp_path / "prog.c"
    src.write_text("void main() {\n  printf(1+2);\n}\n")
    out = tmp_path / "prog.go"
    assert main(["transpile", "--target", "go", "--version", "v2.3",
                 str(src), "-o", str(out)]) == 0
    assert "fmt.Println(1 + 2)" in out.read_text()


def test_transpile_reports_defect_on_stderr(tmp_path, capsys):
    src = tmp_path / "prog.c"
    src.write_text("void main() {\n  int a = 2+;\n}\n")
    assert main(["transpile", "--target", "julia", "--version", "v2.3",
                 str(src)]) == 0
    captured = capsys.readouterr()
    assert "main()" in captured.out
    assert "[Parser] Unexpected token EOL" in captured.err
    assert "fails at parse" in captured.err


def test_generate_subcommand_without_validation(tmp_path, capsys):
    assert main(["generate", "--target", "go", "--versions", "x1.2",
                 "--out", str(tmp_path), "--no-validate"]) == 0
    assert (tmp_path / "go" / "x1.2" / "tests.yaml").exists()
    assert "go x1.2: 4/4 ok" in capsys.readouterr().out


def test_generate_report_file(tmp_path):
    report = tmp_path / "report.md"
    main(["generate", "--target", "julia", "--versions", "v0.0",
          "--out", str(tmp_path), "--no-validate", "--report", str(report)])
    assert "v0.0: 14/14 equivalent" in report.read_text()


def test_versions_all_resolves_every_corpus_version(tmp_path):
    assert main(["generate", "--target", "go", "--versions", "all",
                 "--out", str(tmp_path), "--no-validate"]) == 0
    generated = {p.name for p in (tmp_path / "go").iterdir()}
    assert {"v0.0", "v2.3", "x3.0"} <= generated


def test_unknown_target_rejected_by_argparse(tmp_path):
    with pytest.raises(SystemExit):
        main(["transpile", "--target", "cobol", str(tmp_path / "x.c")])
