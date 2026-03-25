#!/usr/bin/env python3
import ast
import sys
from pathlib import Path

import libcst as cst
from libcst import matchers as m

TRUE_FALSE_NONE = {"True", "False", "None"}

_DUMMY_MODULE = cst.Module(body=[])


class Malformed(Exception):
    def __init__(self, message="Malformed", *, node):
        try:
            source = _DUMMY_MODULE.code_for_node(node)
        except Exception:
            source = repr(node)
        super().__init__(f"{message}: {source}")


def _normalize_code(node):
    """Get normalized single-line source code for a libcst expression node."""
    source = _DUMMY_MODULE.code_for_node(node)
    return ast.unparse(ast.parse(source, mode="eval").body)


def _is_constant(node):
    """Check if a libcst node is a constant/literal value."""
    return isinstance(node, (cst.Integer, cst.Float, cst.SimpleString))


def _get_assert_method_name(call_node):
    """If call is self.assertXxx(...), return method name. Otherwise None."""
    if not isinstance(call_node, cst.Call):
        return None
    if not m.matches(call_node.func, m.Attribute(value=m.Name("self"))):
        return None
    attr = call_node.func.attr
    name = attr.value if isinstance(attr, cst.Name) else str(attr)
    return name if name in assert_mapping else None


def _get_args(node):
    """Extract (positional_arg_strings, kwarg_strings, raw_positional_nodes)."""
    args = []
    kwargs = []
    raw = []
    for arg in node.args:
        code = _normalize_code(arg.value)
        if arg.keyword is None:
            args.append(code)
            raw.append(arg.value)
        else:
            key = arg.keyword.value
            kwargs.append(f"{key}={code}")
    return args, kwargs, raw


def _parse_args_and_msg(node, required_args_count, *, raise_if_malformed=True):
    args, kwarg_list, raw = _get_args(node)
    msg = ""

    for i, kwarg in enumerate(kwarg_list):
        key, val = kwarg.split("=", 1)
        if key == "msg":
            msg = val
            kwarg_list.pop(i)
            break

    if len(args) > required_args_count and isinstance(args[required_args_count], str):
        msg = args.pop(required_args_count)
        if len(raw) > required_args_count:
            raw.pop(required_args_count)

    if raise_if_malformed and len(args) != required_args_count:
        raise Malformed(node=node)

    return args, kwarg_list, raw, f", {msg}" if msg else ""


def _handle_equal_or_unequal(node, *, is_op, cmp_op):
    args, kwarg_list, raw, msg = _parse_args_and_msg(
        node, 2, raise_if_malformed=False
    )
    if len(args) != 2 or kwarg_list:
        raise Malformed("Potentially malformed", node=node)
    if args[0] in TRUE_FALSE_NONE:
        return f"assert {args[1]} {is_op} {args[0]}{msg}"
    if args[1] in TRUE_FALSE_NONE:
        return f"assert {args[0]} {is_op} {args[1]}{msg}"
    # De-yoda
    if len(raw) >= 2 and _is_constant(raw[0]) and not _is_constant(raw[1]):
        args = [args[1], args[0]]
    return f"assert {args[0]} {cmp_op} {args[1]}{msg}"


def _handle_prefix_or_suffix(node, *, prefix="", suffix=""):
    args, _, _, msg = _parse_args_and_msg(node, 1)
    return f"assert {prefix}{args[0]}{suffix}{msg}"


def _handle_generic_binary(node, *, op):
    args, _, _, msg = _parse_args_and_msg(node, 2)
    return f"assert {args[0]} {op} {args[1]}{msg}"


def _handle_generic_call(node, *, func):
    args, _, _, msg = _parse_args_and_msg(node, 2)
    return f"assert {func}({args[0]}, {args[1]}){msg}"


def _handle_almost_equal(node, *, op):
    args, _, _, msg = _parse_args_and_msg(node, 2)
    return f"assert round({args[0]} - {args[1]}, 7) {op} 0{msg}"


def handle_equal(node):
    return _handle_equal_or_unequal(node, is_op="is", cmp_op="==")


def handle_not_equal(node):
    return _handle_equal_or_unequal(node, is_op="is not", cmp_op="!=")


def handle_true(node):
    return _handle_prefix_or_suffix(node, prefix="")


def handle_false(node):
    return _handle_prefix_or_suffix(node, prefix="not ")


def handle_in(node):
    return _handle_generic_binary(node, op="in")


def handle_not_in(node):
    return _handle_generic_binary(node, op="not in")


def handle_is(node):
    return _handle_generic_binary(node, op="is")


def handle_is_not(node):
    return _handle_generic_binary(node, op="is not")


def handle_is_none(node):
    return _handle_prefix_or_suffix(node, suffix=" is None")


def handle_is_not_none(node):
    return _handle_prefix_or_suffix(node, suffix=" is not None")


def handle_is_instance(node):
    return _handle_generic_call(node, func="isinstance")


def handle_not_is_instance(node):
    return _handle_generic_call(node, func="not isinstance")


def handle_less(node):
    return _handle_generic_binary(node, op="<")


def handle_less_equal(node):
    return _handle_generic_binary(node, op="<=")


def handle_greater(node):
    return _handle_generic_binary(node, op=">")


def handle_greater_equal(node):
    return _handle_generic_binary(node, op=">=")


def handle_almost_equal(node):
    return _handle_almost_equal(node, op=">=")


def handle_not_almost_equal(node):
    return _handle_almost_equal(node, op="!=")


def handle_raises(call_node):
    args, _, _ = _get_args(call_node)
    if len(args) > 2:
        raise Malformed(node=call_node)
    if len(args) == 2:
        return f"pytest.raises({args[0]}, {args[1]})"
    return None


assert_mapping = {
    "assertEqual": handle_equal,
    "assertEquals": handle_equal,
    "assertNotEqual": handle_not_equal,
    "assertNotEquals": handle_not_equal,
    "assert_": handle_true,
    "assertTrue": handle_true,
    "assertFalse": handle_false,
    "assertIn": handle_in,
    "assertNotIn": handle_not_in,
    "assertIs": handle_is,
    "assertIsNot": handle_is_not,
    "assertIsNone": handle_is_none,
    "assertIsNotNone": handle_is_not_none,
    "assertIsInstance": handle_is_instance,
    "assertNotIsInstance": handle_not_is_instance,
    "assertLess": handle_less,
    "assertLessEqual": handle_less_equal,
    "assertGreater": handle_greater,
    "assertGreaterEqual": handle_greater_equal,
    "assertAlmostEqual": handle_almost_equal,
    "assertNotAlmostEqual": handle_not_almost_equal,
    "assertRaises": handle_raises,
}


class UnittestToPytestTransformer(cst.CSTTransformer):
    def __init__(self):
        self.needs_pytest_import = False
        self.has_pytest_import = False

    def visit_Import(self, node):
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            if m.matches(alias.name, m.Name("pytest")):
                self.has_pytest_import = True

    def leave_SimpleStatementLine(self, original_node, updated_node):
        if len(updated_node.body) != 1:
            return updated_node
        stmt = updated_node.body[0]
        if not isinstance(stmt, cst.Expr):
            return updated_node
        if not isinstance(stmt.value, cst.Call):
            return updated_node

        call = stmt.value
        method_name = _get_assert_method_name(call)
        if not method_name:
            return updated_node

        handler = assert_mapping[method_name]
        try:
            result_str = handler(call)
        except Malformed as e:
            print(str(e))
            return updated_node

        if result_str is None:
            return updated_node

        if "pytest." in result_str:
            self.needs_pytest_import = True

        new_stmt = cst.parse_statement(result_str)
        return new_stmt.with_changes(
            leading_lines=updated_node.leading_lines,
            trailing_whitespace=updated_node.trailing_whitespace,
        )

    def leave_With(self, original_node, updated_node):
        if not updated_node.items:
            return updated_node
        first_item = updated_node.items[0]
        call = first_item.item
        if not isinstance(call, cst.Call):
            return updated_node

        if _get_assert_method_name(call) != "assertRaises":
            return updated_node

        self.needs_pytest_import = True

        new_call = call.with_changes(
            func=cst.Attribute(
                value=cst.Name("pytest"),
                attr=cst.Name("raises"),
            )
        )
        new_items = list(updated_node.items)
        new_items[0] = first_item.with_changes(item=new_call)
        return updated_node.with_changes(items=new_items)

    def leave_Module(self, original_node, updated_node):
        if self.needs_pytest_import and not self.has_pytest_import:
            import_stmt = cst.parse_statement("import pytest\n")
            return updated_node.with_changes(
                body=[import_stmt, *updated_node.body]
            )
        return updated_node


def transform_source(source: str) -> str:
    """Transform source code, converting unittest asserts to pytest asserts."""
    tree = cst.parse_module(source)
    transformer = UnittestToPytestTransformer()
    new_tree = tree.visit(transformer)
    return new_tree.code


def transform_file(path: Path) -> bool:
    """Transform a file in-place. Returns True if changes were made."""
    source = path.read_text()
    new_source = transform_source(source)
    if new_source != source:
        path.write_text(new_source)
        return True
    return False


def main():
    if sys.version_info < (3, 9):
        raise RuntimeError("This script requires Python version >=3.9")

    try:
        path = sys.argv[1]
    except IndexError:
        path = "."

    target = Path(path)
    if target.is_file():
        files = [target]
    else:
        files = sorted(target.rglob("*.py"))

    changed = 0
    for f in files:
        if transform_file(f):
            print(f"Transformed: {f}")
            changed += 1

    print(f"\nTransformed {changed} file(s).")
    print("HINT: Consider running a formatter to correctly format your new assertions!")


if __name__ == "__main__":
    main()
