"""README must link the DS image for the version; language is optional."""
from compiler_testing_lib.runner import DS_URL, ds_link_ok


def test_plain_version_link():
    assert ds_link_ok(f"![DS]({DS_URL}?version=v2.1)", "v2.1", "go")


def test_language_suffix():
    assert ds_link_ok(f"{DS_URL}?version=v2.1&language=go", "v2.1", "go")


def test_language_case_insensitive():
    assert ds_link_ok(f"{DS_URL}?version=v2.1&language=GO", "v2.1", "Go")


def test_parameters_in_any_order():
    assert ds_link_ok(f"{DS_URL}?language=go&version=v2.1", "v2.1", "go")


def test_html_img_with_escaped_ampersand():
    readme = f'<img src="{DS_URL}?version=v2.1&amp;language=go" alt="DS">'
    assert ds_link_ok(readme, "v2.1", "go")


def test_wrong_language_rejected():
    assert not ds_link_ok(f"{DS_URL}?version=v2.1&language=c", "v2.1", "go")


def test_wrong_version_rejected():
    assert not ds_link_ok(f"{DS_URL}?version=v2.0&language=go", "v2.1", "go")


def test_missing_link_rejected():
    assert not ds_link_ok("# My compiler\n\nno diagram here", "v2.1", "go")


def test_one_good_link_among_others_is_enough():
    readme = f"{DS_URL}?version=v1.0\n{DS_URL}?version=v2.1&language=go\n"
    assert ds_link_ok(readme, "v2.1", "go")
