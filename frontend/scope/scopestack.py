from typing import Optional

from frontend.symbol.symbol import Symbol
from frontend.symbol.funcsymbol import FuncSymbol
from utils.error import *

from .scope import Scope
from .globalscope import GlobalScopeType


class ScopeStack:
    def __init__(self) -> None:
        self.stack = []
        self.loopcnt = 0

    def push(self, scope: Scope) -> None:
        self.stack.append(scope)

    def pop(self) -> None:
        self.stack.pop()

    def declare(self, symbol: Symbol) -> None:
        scope = self.stack[-1]
        if scope.containsKey(symbol.name):
            raise DecafDeclConflictError(symbol.name)
        if len(self.stack) == 2 and self.stack[0].containsKey(symbol.name):
            raise DecafDeclConflictError(symbol.name)
        scope.declare(symbol)

    def lookup(self, name: str) -> Optional[Symbol]:
        for scope in self.stack[::-1]:
            result = scope.lookup(name)
            if result:
                return result
        return None

    def findConflict(self, name: str) -> Optional[Symbol]:
        scope = self.stack[-1]
        if scope.containsKey(name):
            return scope.lookup(name)
        return None