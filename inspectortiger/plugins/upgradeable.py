"""
## Upgradeable
Improvable (for 3.8+) syntaxes

"""

__author__ = "Batuhan Taskaya"

import ast

from inspectortiger.config_manager import Plugin
from inspectortiger.inspector import Inspector
from inspectortiger.plugins.context import Contexts, get_context
from inspectortiger.utils import (
    biname_check,
    constant_check,
    is_single_node,
    name_check,
    target_check,
)


@Inspector.register(ast.For)
def yield_from(node, db):
    """`yield` can be replaced with `yield from`.

    ```py
    for x in y:
        yield x
    ```
    to
    ```py
    yield from y
    ```
    """

    if (
        is_single_node(node, ast.Expr)
        and isinstance(node.body[0].value, ast.Yield)
        and target_check(node.body[0].value.value, node.target)
    ):
        return node.body[0].value


@Inspector.register(ast.Subscript)
def optional(node, db):
    """`Union[Type, None]` can be replaced with `Optional[Type]`.

    ```py
    def foo(x: Union[str, None]): ...
    ```
    to
    ```py
    def foo(x: Optional[str]): ...
    ```
    """

    if (
        name_check(node.value, "Union")
        and isinstance(node.slice.value, ast.Tuple)
        and len(node.slice.value.elts) == 2
        and len(
            list(
                filter(
                    lambda node: constant_check(node, None),
                    node.slice.value.elts,
                )
            )
        )
    ):
        return node.value


@Inspector.register(ast.Call)
@Plugin.require("@context")
def super_args(node, db):
    """`super(MyClass, self)` can be replaced with `super()`

    ```py
    super(MyClass, self)
    ```
    to
    ```py
    super()
    ```
    """

    return (
        get_context(node, db) is db["context"]["context"]
        and db["context"]["context"].context is Contexts.FUNCTION
        and db["context"]["previous_contexts"][-1].context is Contexts.CLASS
        and name_check(node.func, "super")
        and node.args
    )


@Inspector.register(ast.For)
def builtin_enumerate(node, db):
    """`range(len(iterable))` can be replaced with `enumerate(iterable)`

    ```py
    for index in range(len(iterable)):
        print(index, iterable[index])
    ```
    to
    ```py
    for index, item in enumerate(iterable):
        print(index, item)
    ```
    """

    if (
        isinstance(node.iter, ast.Call)
        and name_check(node.iter.func, "range")
        and len(node.iter.args) == 1
        and isinstance(node.iter.args[0], ast.Call)
        and name_check(node.iter.args[0].func, "len")
        and len(node.iter.args[0].args) == 1
    ):
        target = node.target
        iterable = node.iter.args[0].args[0]
        for subnode in ast.walk(node):
            if (
                isinstance(subnode, ast.Subscript)
                and isinstance(subnode.slice, ast.Index)
                and biname_check(subnode.value, iterable)
                and biname_check(subnode.slice.value, target)
            ):
                return node.iter
