# Temporary variables.
class Temp:
    def __init__(self, index: int) -> None:
        self.index = index
        self.argOrder1 = 0
        self.argOrder2 = 0

    def __str__(self) -> str:
        return "_T" + str(self.index)
