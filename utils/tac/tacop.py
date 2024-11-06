from enum import Enum, auto, unique


# Kinds of instructions.
@unique
class InstrKind(Enum):
    # Labels.
    LABEL = auto()
    # Sequential instructions (unary operations, binary operations, etc).
    SEQ = auto()
    # Branching instructions.
    JMP = auto()
    # Branching with conditions.
    COND_JMP = auto()
    # Return instruction.
    RET = auto()


# Kinds of unary operations.
@unique
class TacUnaryOp(Enum):
    NEG = auto()
    BITNOT = auto()
    LOGICNOT = auto()

# Kinds of binary operations.
@unique
class TacBinaryOp(Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    MOD = auto()
    BEQ = auto()
    BNE = auto()
    SLT = auto()
    BLE = auto()
    SGT = auto()
    BGE = auto()
    LAND = auto()
    LOR = auto()

    # TODO: Get rid of the old ones
    REM = auto()
    EQU = auto()
    NEQ = auto()
    LEQ = auto()
    GEQ = auto()
    AND = auto()
    OR = auto()
    BITAND = auto()
    BITOR = auto()
    XOR = auto()


# Kinds of branching with conditions.
@unique
class CondBranchOp(Enum):
    BEQ = auto()
    BNE = auto()
