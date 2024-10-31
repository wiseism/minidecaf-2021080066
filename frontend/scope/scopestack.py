from typing import Optional
from frontend.symbol.symbol import Symbol
from .scope import Scope

# ScopeStackOverflow is raised when the scope stack overflows.
class ScopeStackOverflow(Exception):
    ...

class ScopeStack:
    defaultMaxScopeDepth = 256

    def __init__(
        self, globalscope: Scope, scopeDepth: int = defaultMaxScopeDepth
    ) -> None:
        self.globalscope = globalscope
        self.stack = [globalscope]
        self.scopeDepth = scopeDepth

    def currentScope(self) -> Scope:
        if not self.stack:
            return self.globalscope
        return self.stack[-1]

    def open(self, scope: Scope) -> None:
        if len(self.stack) < self.scopeDepth:
            self.stack.append(scope)
        else:
            raise ScopeStackOverflow

    def close(self) -> None:
        self.stack.pop()

    # Check if it is in the global scope.
    def isGlobalScope(self) -> bool:
        return self.currentScope().isGlobalScope()

    # Declare a new symbol in the current scope.
    def declare(self, symbol: Symbol) -> None:
        self.currentScope().declare(symbol)

    # Find if there is a name conflict in the current scope.
    def findConflict(self, name: str) -> Optional[Symbol]:
        if self.currentScope().containsKey(name):
            return self.currentScope().get(name)
        return None

    # Find the symbol via name from top to bottom.
    def lookup(self, name: str) -> Optional[Symbol]:
        stackSize = len(self.stack)
        for d in range(stackSize - 1, -1, -1):
            scope = self.stack[d]
            if scope.containsKey(name):
                return scope.get(name)
        return None


