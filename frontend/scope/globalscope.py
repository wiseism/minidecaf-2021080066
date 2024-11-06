from frontend.symbol.symbol import Symbol

from .scope import Scope, ScopeKind
from utils.error import *

"""
Global scope stores all symbols of global variables and functions.
"""


class GlobalScopeType(Scope):
    def __init__(self) -> None:
        super().__init__(ScopeKind.GLOBAL)
        self.definedGlobalVar = {}

    def isGlobalScope(self) -> bool:
        return True

    def define(self, symbol: Symbol) -> None:
        self.definedGlobalVar[symbol.name] = True

    def isDefined(self, symbol: Symbol) -> bool:
        return symbol.name in self.definedGlobalVar

    def declarefunc(self, symbol: Symbol) -> None:
        ori_symbol = self.lookup(symbol.name)
        if ori_symbol:
            if ori_symbol.parameterNum != symbol.parameterNum:
                raise DecafDeclConflictError(symbol.name + " para num")
            for i in range(0, ori_symbol.parameterNum):
                if not ori_symbol.getParaType(i).name == symbol.getParaType(i).name:
                    raise DecafDeclConflictError(symbol.name + " para type")
        else:
            self.symbols[symbol.name] = symbol

    def definefunc(self, symbol: Symbol) -> None:
        if self.isDefined(symbol):
            raise DecafDeclConflictError(symbol.name + " redefined")
        self.define(symbol)
        ori_symbol = self.lookup(symbol.name)
        if ori_symbol:
            if ori_symbol.parameterNum != symbol.parameterNum:
                raise DecafDeclConflictError(symbol.name + " para num")
            for i in range(0, ori_symbol.parameterNum):
                if not ori_symbol.getParaType(i).name == symbol.getParaType(i).name:
                    raise DecafDeclConflictError(symbol.name + " para type")
        else:
            self.symbols[symbol.name] = symbol

"""
You can access global scope via GlobalScope. This should be the only instance of GlobalScopeType.
"""
GlobalScope = GlobalScopeType()
