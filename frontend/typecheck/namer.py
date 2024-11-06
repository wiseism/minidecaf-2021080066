from typing import Protocol, TypeVar, cast

from frontend.ast.node import T, Node, NullType, Optional
from frontend.ast.tree import *
from frontend.ast.tree import T, FunctionDeclaration, Optional
from frontend.ast.visitor import T, RecursiveVisitor, Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.symbol.symbol import Symbol
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from frontend.type.type import DecafType
from utils.error import *
from utils.riscv import MAX_INT

"""
The namer phase: resolve all symbols defined in the abstract 
syntax tree and store them in symbol tables (i.e. scopes).
"""


class Namer(Visitor[ScopeStack, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> Program:
        # Global scope. You don't have to consider it until Step 6.
        ctx = GlobalScope

        program.accept(self, ctx)
        return program

    def visitProgram(self, program: Program, ctx: Scope) -> None:
        # Check if the 'main' function is missing
        if not program.hasMainFunc():
            raise DecafNoMainFuncError

        for funcdecl in program.functiondeclarations():
            funcdecl.accept(self, ctx)

        for func in program.functiondefines():
            func.accept(self, ctx)

    def visitFunctionDeclaration(self, funcdecl: FunctionDeclaration, ctx: Scope) -> None:
        funcsymbol = FuncSymbol(funcdecl.ident.value, funcdecl.ret_t)
        for para in funcdecl.para:
            funcsymbol.addParaType(para.var_t.type)
        ctx.declarefunc(funcsymbol)

    def visitFunction(self, func: Function, ctx: Scope) -> None:
        funcctx = ScopeStack()
        funcsymbol = FuncSymbol(func.ident.value, func.ret_t)
        for para in func.para:
            funcsymbol.addParaType(para.var_t.type)
        ctx.definefunc(funcsymbol)
        funcctx.push(Scope(ScopeKind.PARA))
        for para in func.para:
            para.accept(self, funcctx)
        func.body.accept(self, funcctx)
        funcctx.pop()

    def visitParameter(self, para: Parameter, ctx: ScopeStack) -> None:
        symbol = VarSymbol(para.ident.value, para.var_t.type)
        ctx.declare(symbol)
        para.ident.setattr("symbol", symbol)

    def visitCall(self, call: Call, ctx: ScopeStack) -> None:
        if ctx.lookup(call.ident.value):
            raise DecafDeclConflictError(call.ident.value)
        funcsymbol = GlobalScope.lookup(call.ident.value)
        if funcsymbol:
            if funcsymbol.parameterNum != len(call.para):
                raise DecafUndefinedFuncError(call.ident.value)
        else:
            raise DecafUndefinedFuncError(call.ident.value)
        for expr in call.para:
            expr.accept(self, ctx)

    def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
        ctx.push(Scope(ScopeKind.LOCAL))
        for child in block:
            child.accept(self, ctx)
        ctx.pop()

    def visitReturn(self, stmt: Return, ctx: ScopeStack) -> None:
        stmt.expr.accept(self, ctx)

    def visitFor(self, stmt: For, ctx: ScopeStack) -> None:
        ctx.push(Scope(ScopeKind.LOCAL))
        stmt.init.accept(self, ctx)
        stmt.cond.accept(self, ctx)
        stmt.update.accept(self, ctx)
        ctx.loopcnt += 1
        stmt.body.accept(self, ctx)
        ctx.loopcnt -= 1
        ctx.pop()

    def visitIf(self, stmt: If, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        stmt.then.accept(self, ctx)

        if not stmt.otherwise is NULL:
            stmt.otherwise.accept(self, ctx)

    def visitWhile(self, stmt: While, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        ctx.loopcnt += 1
        stmt.body.accept(self, ctx)
        ctx.loopcnt -= 1

    def visitBreak(self, stmt: Break, ctx: ScopeStack) -> None:
        if ctx.loopcnt <= 0:
            raise DecafBreakOutsideLoopError

    def visitContinue(self, stmt: Continue, ctx: ScopeStack) -> None:
        if ctx.loopcnt <= 0:
            raise DecafContinueOutsideLoopError

    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find if a variable with the same name has been declared.
        2. If not, build a new VarSymbol, and put it into the current scope using ctx.declare.
        3. Set the 'symbol' attribute of decl.
        4. If there is an initial value, visit it.
        """
        if ctx.findConflict(decl.ident.value) is not None:
            raise DecafDeclConflictError(decl.ident.value)

        var = VarSymbol(decl.ident.value, decl.var_t.type)
        ctx.declare(var)
        decl.setattr('symbol', var)
        decl.setattr('type', var.type)
        decl.ident.type = var.type
        if decl.init_expr is not NULL:
            decl.init_expr.accept(self, ctx)

    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        if not isinstance(expr.lhs, Identifier):
            raise DecafBadAssignTypeError
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitUnary(self, expr: Unary, ctx: ScopeStack) -> None:
        expr.operand.accept(self, ctx)

    def visitBinary(self, expr: Binary, ctx: ScopeStack) -> None:
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)

    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find the symbol corresponding to ident.
        2. If it has not been declared, raise a DecafUndefinedVarError.
        3. Set the 'symbol' attribute of ident.
        """
        symbol = ctx.lookup(ident.value)
        if symbol:
            ident.setattr("symbol", symbol)
        else:
            raise DecafUndefinedVarError(ident.value)

    def visitIntLiteral(self, expr: IntLiteral, ctx: ScopeStack) -> None:
        value = expr.value
        if value > MAX_INT:
            raise DecafBadIntValueError(value)
