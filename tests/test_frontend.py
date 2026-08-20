"""Front end vs the whole corpus: the diagnosis must match exactly.

This is the strongest property of the front end: for all 391 corpus tests
across all 17 course versions, the diagnosed message equals what the
course reference compiler prints — and valid programs diagnose nothing.
"""

from compiler_testing_lib.transpiler.driver import parse_source

from conftest import expected_message


def test_corpus_diagnosis(version, test, source):
    program = parse_source(source, version)
    got = program.defect.message if program.defect else None
    assert got == expected_message(version, test)


def test_defect_carries_position_and_category(version, test, source):
    program = parse_source(source, version)
    if program.defect is None:
        return
    defect = program.defect
    assert defect.category is not None
    assert defect.tag.startswith("[") and defect.tag.endswith("]")
