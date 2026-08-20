"""GoPrinter: Go AST → source text (gofmt-flavored: tabs, K&R braces).

Expression parenthesization is structure-driven: a binary child is wrapped
whenever Go's precedence would regroup it (notably ``^``, which the course
binds tighter than ``+`` while Go puts them on the same level).
"""

from __future__ import annotations

from ..printer import Printer
from . import nodes as go

_PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 3, ">": 3,
         "+": 4, "-": 4, "^": 4, "*": 5, "/": 5}


class GoPrinter(Printer):
    # -- expressions -------------------------------------------------------
    def expr(self, node) -> str:
        method = getattr(self, f"expr_{type(node).__name__}")
        return method(node)

    def expr_GoLit(self, node: go.GoLit) -> str:
        return node.text

    def expr_GoName(self, node: go.GoName) -> str:
        return node.name

    def expr_GoField(self, node: go.GoField) -> str:
        return f"{self.expr(node.obj)}.{node.name}"

    def expr_GoCall(self, node: go.GoCall) -> str:
        args = ", ".join(self.expr(a) for a in node.args)
        return f"{node.func}({args})"

    def expr_GoUn(self, node: go.GoUn) -> str:
        inner = self.expr(node.operand)
        if isinstance(node.operand, (go.GoBin, go.GoUn)):
            inner = f"({inner})"
        return f"{node.op}{inner}"

    def expr_GoBin(self, node: go.GoBin) -> str:
        prec = _PREC[node.op]

        def side(child, is_right: bool) -> str:
            text = self.expr(child)
            if isinstance(child, go.GoBin):
                child_prec = _PREC[child.op]
                same_op_chain = child.op == node.op and not is_right \
                    and node.op in ("+", "*", "&&", "||")
                if child_prec < prec or (child_prec == prec
                                         and not same_op_chain):
                    return f"({text})"
            return text

        return f"{side(node.left, False)} {node.op} {side(node.right, True)}"

    def expr_Raw(self, node) -> str:
        return node.text

    # -- statements --------------------------------------------------------
    def block_inner(self, node: go.GoBlock) -> list[str]:
        """The statements of a block, unbraced — for constructs (func, if,
        for) that print their own braces around the body."""
        inner: list[str] = []
        for stmt in node.stmts:
            inner.extend(self.lines(stmt))
        return inner

    def lines_GoBlock(self, node: go.GoBlock) -> list[str]:
        # a block used AS a statement keeps its braces: it scopes
        return ["{", *self.indented(self.block_inner(node)), "}"]

    def lines_GoVarDecl(self, node: go.GoVarDecl) -> list[str]:
        decl = f"var {node.name} {node.go_type}"
        if node.init is not None:
            decl += f" = {self.expr(node.init)}"
        out = [decl]
        if node.blank_use:
            out.append(f"_ = {node.name}")
        return out

    def lines_GoConstDecl(self, node: go.GoConstDecl) -> list[str]:
        return [f"const {node.name} = {self.expr(node.init)}"]

    def lines_GoAssign(self, node: go.GoAssign) -> list[str]:
        op = ":=" if node.declare else "="
        out = [f"{self.expr(node.target)} {op} {self.expr(node.expr)}"]
        if node.blank_use:
            out.append(f"_ = {self.expr(node.target)}")
        return out

    def lines_GoExprStmt(self, node: go.GoExprStmt) -> list[str]:
        return [self.expr(node.expr)]

    def lines_GoReturn(self, node: go.GoReturn) -> list[str]:
        if node.expr is None:
            return ["return"]
        return [f"return {self.expr(node.expr)}"]

    def lines_GoIf(self, node: go.GoIf) -> list[str]:
        out = [f"if {self.expr(node.cond)} {{"]
        out.extend(self.indented(self.block_inner(node.then)))
        if node.other is not None:
            out.append("} else {")
            out.extend(self.indented(self.block_inner(node.other)))
        out.append("}")
        return out

    def lines_GoFor(self, node: go.GoFor) -> list[str]:
        if node.init is not None or node.post is not None:
            init = "; ".join(self.lines(node.init)[:1]) if node.init else ""
            post = "; ".join(self.lines(node.post)[:1]) if node.post else ""
            cond = self.expr(node.cond) if node.cond is not None else ""
            header = f"for {init}; {cond}; {post} {{"
        elif node.cond is not None:
            header = f"for {self.expr(node.cond)} {{"
        else:
            header = "for {"
        out = [header]
        out.extend(self.indented(self.block_inner(node.body)))
        out.append("}")
        return out

    # -- declarations ------------------------------------------------------
    def lines_GoFunc(self, node: go.GoFunc) -> list[str]:
        params = ", ".join(f"{name} {go_type}"
                           for name, go_type in node.params)
        ret = f" {node.ret}" if node.ret else ""
        out = [f"func {node.name}({params}){ret} {{"]
        out.extend(self.indented(self.block_inner(node.body)))
        out.append("}")
        return out

    def lines_GoStruct(self, node: go.GoStruct) -> list[str]:
        out = [f"type {node.name} struct {{"]
        out.extend(self.indented([f"{name} {go_type}"
                                  for name, go_type in node.fields]))
        out.append("}")
        return out

    def lines_GoFile(self, node: go.GoFile) -> list[str]:
        out = ["package main", ""]
        if node.imports:
            if len(node.imports) == 1:
                out.append(f'import "{node.imports[0]}"')
            else:
                out.append("import (")
                out.extend(self.indented([f'"{imp}"'
                                          for imp in node.imports]))
                out.append(")")
            out.append("")
        for block in node.prelude:
            out.extend(self.lines(block))
            out.append("")
        for decl in node.decls:
            out.extend(self.lines(decl))
            out.append("")
        while out and out[-1] == "":
            out.pop()
        return out
