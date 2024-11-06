from frontend.ast.node import T, Optional
from frontend.ast.tree import T, Continue, Function, Optional, Parameter
from frontend.ast import node
from frontend.ast.tree import *
from frontend.ast.visitor import T, Visitor
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from utils.label.blocklabel import BlockLabel
from utils.label.funclabel import FuncLabel
from utils.tac import tacop
from utils.tac.temp import Temp
from utils.tac.tacinstr import *
from utils.tac.tacfunc import TACFunc
from utils.tac.tacprog import TACProg
from utils.tac.tacvisitor import TACVisitor

"""
The TAC generation phase: translate the abstract syntax tree into three-address code.
"""


class LabelManager:
    """
    A global label manager (just a counter).
    We use this to create unique (block) labels accross functions.
    """

    def __init__(self):
        self.nextTempLabelId = 0

    def freshLabel(self) -> BlockLabel:
        self.nextTempLabelId += 1
        return BlockLabel(str(self.nextTempLabelId))


class TACFuncEmitter(TACVisitor):
    """
    Translates a minidecaf (AST) function into low-level TAC function.
    """

    def __init__(
            self, entry: FuncLabel, numArgs: int, labelManager: LabelManager
    ) -> None:
        self.labelManager = labelManager
        self.func = TACFunc(entry, numArgs)
        self.visitLabel(entry)
        self.nextTempId = 0

        self.continueLabelStack = []
        self.breakLabelStack = []

    # To get a fresh new temporary variable.
    def freshTemp(self) -> Temp:
        temp = Temp(self.nextTempId)
        self.nextTempId += 1
        return temp

    # To get a fresh new label (for jumping and branching, etc).
    def freshLabel(self) -> Label:
        return self.labelManager.freshLabel()

    # To count how many temporary variables have been used.
    def getUsedTemp(self) -> int:
        return self.nextTempId

    # In fact, the following methods can be named 'appendXXX' rather than 'visitXXX'.
    # E.g., by calling 'visitAssignment', you add an assignment instruction at the end of current function.
    def visitAssignment(self, dst: Temp, src: Temp) -> Temp:
        self.func.add(Assign(dst, src))
        return dst

    def visitLoad(self, value: Union[int, str]) -> Temp:
        temp = self.freshTemp()
        self.func.add(LoadImm4(temp, value))
        return temp

    def visitUnary(self, op: UnaryOp, operand: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Unary(op, temp, operand))
        return temp

    def visitUnarySelf(self, op: UnaryOp, operand: Temp) -> None:
        self.func.add(Unary(op, operand, operand))

    def visitBinary(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> Temp:
        temp = self.freshTemp()
        self.func.add(Binary(op, temp, lhs, rhs))
        return temp

    def visitBinarySelf(self, op: BinaryOp, lhs: Temp, rhs: Temp) -> None:
        self.func.add(Binary(op, lhs, lhs, rhs))

    def visitBranch(self, target: Label) -> None:
        self.func.add(Branch(target))

    def visitCondBranch(self, op: CondBranchOp, cond: Temp, target: Label) -> None:
        self.func.add(CondBranch(op, cond, target))

    def visitReturn(self, value: Optional[Temp]) -> None:
        self.func.add(Return(value))

    def visitLabel(self, label: Label) -> None:
        self.func.add(Mark(label))

    def visitMemo(self, content: str) -> None:
        self.func.add(Memo(content))

    def visitRaw(self, instr: TACInstr) -> None:
        self.func.add(instr)

    def visitEnd(self) -> TACFunc:
        if (len(self.func.instrSeq) == 0) or (not self.func.instrSeq[-1].isReturn()):
            self.func.add(Return(None))
        self.func.tempUsed = self.getUsedTemp()
        return self.func

    # To open a new loop (for break/continue statements)
    def openLoop(self, breakLabel: Label, continueLabel: Label) -> None:
        self.breakLabelStack.append(breakLabel)
        self.continueLabelStack.append(continueLabel)

    # To close the current loop.
    def closeLoop(self) -> None:
        self.breakLabelStack.pop()
        self.continueLabelStack.pop()

    # To get the label for 'break' in the current loop.
    def getBreakLabel(self) -> Label:
        return self.breakLabelStack[-1]

    # To get the label for 'continue' in the current loop.
    def getContinueLabel(self) -> Label:
        return self.continueLabelStack[-1]

    def visitParam(self, para: Temp) -> None:
        self.func.add(Param(para))

    def visitCall(self, func: Label, argNum: int) -> Temp:
        temp = self.freshTemp()
        self.func.add(Callinstr(temp, func, argNum))
        return temp


class TACGen(Visitor[TACFuncEmitter, None]):
    # Entry of this phase
    def transform(self, program: Program) -> TACProg:
        labelManager = LabelManager()
        tacFuncs = []
        for funcName, astFunc in program.functions().items():
            # in step9, you need to use real parameter count
            emitter = TACFuncEmitter(FuncLabel(funcName), 0, labelManager)
            for para in astFunc.para:
                para.accept(self, emitter)
            astFunc.body.accept(self, emitter)
            tacFuncs.append(emitter.visitEnd())
        return TACProg(tacFuncs)

    def visitParameter(self, para: Parameter, mv: TACFuncEmitter) -> None:
        temp = mv.freshTemp()
        mv.func.numArgs += 1
        temp.argOrder1 = mv.func.numArgs
        mv.func.argTemps.append(temp)
        # print(temp, temp.argOrder)
        symbol = para.ident.getattr("symbol")
        symbol.temp = temp

    def visitCall(self, call: Call, mv: TACFuncEmitter) -> None:
        lenth = len(call.para)
        temps = []
        for index in range(0, lenth):
            para = call.para[index]
            para.accept(self, mv)
            temp = para.getattr("val")
            temp.argOrder2 = -1 * (index + 1)
            temps.append(temp)
            # print(temp, temp.argOrder)
        for temp in temps[::-1]:
            mv.visitParam(temp)
        call.setattr("val", mv.visitCall(FuncLabel(call.ident.value), len(call.para)))

    def visitBlock(self, block: Block, mv: TACFuncEmitter) -> None:
        for child in block:
            child.accept(self, mv)

    def visitReturn(self, stmt: Return, mv: TACFuncEmitter) -> None:
        stmt.expr.accept(self, mv)
        mv.visitReturn(stmt.expr.getattr("val"))

    def visitBreak(self, stmt: Break, mv: TACFuncEmitter) -> None:
        mv.visitBranch(mv.getBreakLabel())

    def visitContinue(self, stmt: Continue, mv: TACFuncEmitter) -> None:
        mv.visitBranch(mv.getContinueLabel())

    def visitIdentifier(self, ident: Identifier, mv: TACFuncEmitter) -> None:
        symbol: VarSymbol = ident.getattr("symbol")
        ident.setattr("val", symbol.temp)

    def visitDeclaration(self, decl: Declaration, mv: TACFuncEmitter) -> None:
        symbol: VarSymbol = decl.getattr("symbol")
        temp = mv.freshTemp()
        symbol.temp = temp
        if decl.init_expr:
            decl.init_expr.accept(self, mv)
            mv.visitAssignment(temp, decl.init_expr.getattr("val"))

    def visitAssignment(self, expr: Assignment, mv: TACFuncEmitter) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)
        symbol: VarSymbol = expr.lhs.getattr("symbol")
        expr.setattr("val", mv.visitAssignment(symbol.temp, expr.rhs.getattr("val")))

    def visitIf(self, stmt: If, mv: TACFuncEmitter) -> None:
        stmt.cond.accept(self, mv)

        if stmt.otherwise is NULL:
            skipLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitLabel(skipLabel)
        else:
            skipLabel = mv.freshLabel()
            exitLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitBranch(exitLabel)
            mv.visitLabel(skipLabel)
            stmt.otherwise.accept(self, mv)
            mv.visitLabel(exitLabel)

    def visitWhile(self, stmt: While, mv: TACFuncEmitter) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitFor(self, stmt: For, mv: TACFuncEmitter) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        stmt.init.accept(self, mv)
        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        stmt.update.accept(self, mv)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitUnary(self, expr: Unary, mv: TACFuncEmitter) -> None:
        expr.operand.accept(self, mv)

        op = {
            node.UnaryOp.Neg: tacop.TacUnaryOp.NEG,
            node.UnaryOp.LogicNot: tacop.TacUnaryOp.LOGICNOT,
            node.UnaryOp.BitNot: tacop.TacUnaryOp.BITNOT,
        }[expr.op]
        expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))

    def visitBinary(self, expr: Binary, mv: TACFuncEmitter) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)

        if expr.op == node.BinaryOp.LogicAnd:
            temp = mv.freshTemp()
            skipLable = mv.freshLabel()
            exitLable = mv.freshLabel()
            mv.visitCondBranch(CondBranchOp.BEQ, expr.lhs.getattr("val"), skipLable)
            mv.visitCondBranch(CondBranchOp.BEQ, expr.rhs.getattr("val"), skipLable)
            temptrue = mv.visitLoad(1)
            mv.visitAssignment(temp, temptrue)
            mv.visitBranch(exitLable)
            mv.visitLabel(skipLable)
            tempfalse = mv.visitLoad(0)
            mv.visitAssignment(temp, tempfalse)
            mv.visitLabel(exitLable)
            expr.setattr("val", temp)
        elif expr.op == node.BinaryOp.LogicOr:
            temp = mv.freshTemp()
            trueLable = mv.freshLabel()
            falseLable = mv.freshLabel()
            exitLable = mv.freshLabel()
            mv.visitCondBranch(CondBranchOp.BNE, expr.lhs.getattr("val"), trueLable)
            mv.visitCondBranch(CondBranchOp.BEQ, expr.rhs.getattr("val"), falseLable)
            mv.visitLabel(trueLable)
            temptrue = mv.visitLoad(1)
            mv.visitAssignment(temp, temptrue)
            mv.visitBranch(exitLable)
            mv.visitLabel(falseLable)
            tempfalse = mv.visitLoad(0)
            mv.visitAssignment(temp, tempfalse)
            mv.visitLabel(exitLable)
            expr.setattr("val", temp)
        else:
            op = {
                node.BinaryOp.Add: tacop.TacBinaryOp.ADD,
                node.BinaryOp.Sub: tacop.TacBinaryOp.SUB,
                node.BinaryOp.Mul: tacop.TacBinaryOp.MUL,
                node.BinaryOp.Div: tacop.TacBinaryOp.DIV,
                node.BinaryOp.Mod: tacop.TacBinaryOp.MOD,
                node.BinaryOp.EQ: tacop.TacBinaryOp.EQU,
                node.BinaryOp.NE: tacop.TacBinaryOp.NEQ,
                node.BinaryOp.LT: tacop.TacBinaryOp.SLT,
                node.BinaryOp.GT: tacop.TacBinaryOp.SGT,
                node.BinaryOp.LE: tacop.TacBinaryOp.LEQ,
                node.BinaryOp.GE: tacop.TacBinaryOp.GEQ,
                node.BinaryOp.BitAnd: tacop.TacBinaryOp.BITAND,
                node.BinaryOp.BitOr: tacop.TacBinaryOp.BITOR,
                node.BinaryOp.Xor: tacop.TacBinaryOp.XOR,
            }[expr.op]
            expr.setattr(
                "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
            )

    def visitCondExpr(self, expr: ConditionExpression, mv: TACFuncEmitter) -> None:
        expr.cond.accept(self, mv)
        temp = mv.freshTemp()
        skipLable = mv.freshLabel()
        exitLable = mv.freshLabel()
        mv.visitCondBranch(CondBranchOp.BEQ, expr.cond.getattr("val"), skipLable)
        expr.then.accept(self, mv)
        mv.visitAssignment(temp, expr.then.getattr("val"))
        mv.visitBranch(exitLable)
        mv.visitLabel(skipLable)
        expr.otherwise.accept(self, mv)
        mv.visitAssignment(temp, expr.otherwise.getattr("val"))
        mv.visitLabel(exitLable)
        expr.setattr("val", temp)

    def visitIntLiteral(self, expr: IntLiteral, mv: TACFuncEmitter) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))
