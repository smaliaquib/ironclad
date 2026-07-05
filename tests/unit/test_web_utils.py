from tools import _web_utils


def test_strip_tags_removes_markup():
    html = "<div><p>Hello <b>world</b></p></div>"
    assert _web_utils.strip_tags(html) == "Hello world"


def test_strip_tags_removes_script_and_style_content():
    html = "<html><style>.a{color:red}</style><script>alert(1)</script><p>Visible</p></html>"
    assert _web_utils.strip_tags(html) == "Visible"


def test_strip_tags_collapses_whitespace():
    html = "<p>Line one</p>\n\n<p>   Line   two   </p>"
    assert _web_utils.strip_tags(html) == "Line one Line two"
