import pytest

from codemod_unittest_to_pytest_asserts import transform_source

WRAP_TEMPLATE = """\
class T:
    def t(self):
        {line}
"""


def _transform_line(line):
    """Transform a single assertion line inside a class method, return just that line."""
    source = WRAP_TEMPLATE.format(line=line)
    result = transform_source(source)
    # Extract the body line (strip the class/def wrapper)
    lines = result.splitlines()
    # Find the assertion line(s) — skip import, class def, method def
    body_lines = [l for l in lines if l.startswith("        ")]
    return "\n".join(l.strip() for l in body_lines)


CASES = [
    pytest.param(
        "self.assertEqual(1, 2)",
        "assert 1 == 2",
        id="assertEqual-basic",
    ),
    pytest.param(
        "self.assertEquals(1, 2)",
        "assert 1 == 2",
        id="assertEquals-alias",
    ),
    pytest.param(
        'self.assertEqual(1, 2, "oops")',
        "assert 1 == 2, 'oops'",
        id="assertEqual-positional-msg",
    ),
    pytest.param(
        'self.assertEqual(1, 2, msg="oops")',
        "assert 1 == 2, 'oops'",
        id="assertEqual-kwarg-msg",
    ),
    pytest.param(
        "self.assertEqual(foo, True)",
        "assert foo is True",
        id="assertEqual-true-rhs",
    ),
    pytest.param(
        "self.assertEqual(True, foo)",
        "assert foo is True",
        id="assertEqual-true-lhs",
    ),
    pytest.param(
        "self.assertEqual(foo, False)",
        "assert foo is False",
        id="assertEqual-false-rhs",
    ),
    pytest.param(
        "self.assertEqual(foo, None)",
        "assert foo is None",
        id="assertEqual-none-rhs",
    ),
    pytest.param(
        "self.assertEqual(None, foo)",
        "assert foo is None",
        id="assertEqual-none-lhs",
    ),
    pytest.param(
        "self.assertEqual('bar', foo)",
        "assert foo == 'bar'",
        id="assertEqual-de-yoda-string",
    ),
    pytest.param(
        "self.assertEqual(42, foo)",
        "assert foo == 42",
        id="assertEqual-de-yoda-int",
    ),
    pytest.param(
        "self.assertEqual(1, 2)",
        "assert 1 == 2",
        id="assertEqual-both-constants-no-swap",
    ),
    pytest.param(
        "self.assertEqual(foo, bar)",
        "assert foo == bar",
        id="assertEqual-both-names-no-swap",
    ),
    pytest.param(
        "self.assertNotEqual(1, 2)",
        "assert 1 != 2",
        id="assertNotEqual-basic",
    ),
    pytest.param(
        "self.assertNotEquals(a, b)",
        "assert a != b",
        id="assertNotEquals-alias",
    ),
    pytest.param(
        "self.assertNotEqual(foo, None)",
        "assert foo is not None",
        id="assertNotEqual-none",
    ),
    pytest.param(
        "self.assertTrue(x)",
        "assert x",
        id="assertTrue",
    ),
    pytest.param(
        "self.assert_(x)",
        "assert x",
        id="assert_",
    ),
    pytest.param(
        "self.assertFalse(x)",
        "assert not x",
        id="assertFalse",
    ),
    pytest.param(
        'self.assertTrue(x, "should be true")',
        "assert x, 'should be true'",
        id="assertTrue-with-msg",
    ),
    pytest.param(
        'self.assertIn("a", "abc")',
        "assert 'a' in 'abc'",
        id="assertIn",
    ),
    pytest.param(
        'self.assertNotIn("x", "abc")',
        "assert 'x' not in 'abc'",
        id="assertNotIn",
    ),
    pytest.param(
        "self.assertIs(a, b)",
        "assert a is b",
        id="assertIs",
    ),
    pytest.param(
        "self.assertIsNot(a, b)",
        "assert a is not b",
        id="assertIsNot",
    ),
    pytest.param(
        "self.assertIsNone(x)",
        "assert x is None",
        id="assertIsNone",
    ),
    pytest.param(
        "self.assertIsNotNone(x)",
        "assert x is not None",
        id="assertIsNotNone",
    ),
    pytest.param(
        "self.assertIsInstance(x, int)",
        "assert isinstance(x, int)",
        id="assertIsInstance",
    ),
    pytest.param(
        "self.assertNotIsInstance(x, str)",
        "assert not isinstance(x, str)",
        id="assertNotIsInstance",
    ),
    pytest.param(
        "self.assertLess(1, 2)",
        "assert 1 < 2",
        id="assertLess",
    ),
    pytest.param(
        "self.assertLessEqual(2, 2)",
        "assert 2 <= 2",
        id="assertLessEqual",
    ),
    pytest.param(
        "self.assertGreater(3, 2)",
        "assert 3 > 2",
        id="assertGreater",
    ),
    pytest.param(
        "self.assertGreaterEqual(4, 3)",
        "assert 4 >= 3",
        id="assertGreaterEqual",
    ),
    pytest.param(
        "self.assertAlmostEqual(1.0, 1.1)",
        "assert round(1.0 - 1.1, 7) >= 0",
        id="assertAlmostEqual",
    ),
    pytest.param(
        "self.assertNotAlmostEqual(1.0, 2.0)",
        "assert round(1.0 - 2.0, 7) != 0",
        id="assertNotAlmostEqual",
    ),
    pytest.param(
        "self.assertRaises(ValueError, foo)",
        "pytest.raises(ValueError, foo)",
        id="assertRaises-expression-2arg",
    ),
    pytest.param(
        "self.do_something(1, 2)",
        "self.do_something(1, 2)",
        id="non-assert-call-unchanged",
    ),
    pytest.param(
        "foo(1, 2)",
        "foo(1, 2)",
        id="plain-call-unchanged",
    ),
]


@pytest.mark.parametrize("input_line, expected_line", CASES)
def test_transform(input_line, expected_line):
    result = _transform_line(input_line)
    assert result == expected_line


WITH_CASES = [
    pytest.param(
        """\
class T:
    def t(self):
        with self.assertRaises(ValueError):
            foo()
""",
        """\
import pytest
class T:
    def t(self):
        with pytest.raises(ValueError):
            foo()
""",
        id="with-assertRaises",
    ),
    pytest.param(
        """\
class T:
    def t(self):
        with self.assertRaises(ZeroDivisionError) as exc:
            x = 1 / 0
""",
        """\
import pytest
class T:
    def t(self):
        with pytest.raises(ZeroDivisionError) as exc:
            x = 1 / 0
""",
        id="with-assertRaises-as",
    ),
]


@pytest.mark.parametrize("source, expected", WITH_CASES)
def test_transform_with(source, expected):
    assert transform_source(source) == expected


def test_import_pytest_added_when_needed():
    source = """\
class T:
    def t(self):
        with self.assertRaises(ValueError):
            pass
"""
    result = transform_source(source)
    assert result.startswith("import pytest\n")


def test_import_pytest_not_duplicated():
    source = """\
import pytest
class T:
    def t(self):
        with self.assertRaises(ValueError):
            pass
"""
    result = transform_source(source)
    assert result.count("import pytest") == 1


def test_import_pytest_not_added_when_unnecessary():
    source = """\
class T:
    def t(self):
        self.assertEqual(1, 1)
"""
    result = transform_source(source)
    assert "import pytest" not in result


def test_inline_comment_preserved():
    source = """\
class T:
    def t(self):
        self.assertEqual(1, 1) # check
"""
    result = transform_source(source)
    assert "assert 1 == 1 # check" in result


def test_with_assertraises_comment_preserved():
    source = """\
class T:
    def t(self):
        with self.assertRaises(ValueError):  # boom
            pass
"""
    result = transform_source(source)
    assert "pytest.raises(ValueError):  # boom" in result


def test_multiline_collapsed():
    source = """\
class T:
    def t(self):
        self.assertEqual(
            foo(
                a=1,
                b=2,
            ),
            True
        )
"""
    result = transform_source(source)
    assert "assert foo(a=1, b=2) is True" in result


def test_no_changes_returns_identical():
    source = """\
class T:
    def t(self):
        x = 1 + 2
"""
    assert transform_source(source) == source
