"""Interpreter mainan dari bagian pertama bab Byterun.

Sebelum menyentuh bytecode sungguhan, bab membangun
mesin tumpukan mini atas "instruction set" berupa dict:

    {"instructions": [("LOAD_VALUE", 0), ...],
     "numbers": [7, 5],
     "names": ["a", "b"]}

Argumen instruksi adalah INDEKS — ke "numbers" untuk
LOAD_VALUE, ke "names" untuk LOAD_NAME / STORE_NAME —
dan parse_argument yang menerjemahkannya. Eksekusi
akhirnya memakai dispatch getattr: metode bernama sama
dengan instruksinya, persis pola yang kelak dipakai
VirtualMachine sungguhan dengan awalan byte_.
"""


class Interpreter:
    def __init__(self):
        self.stack = []
        self.environment = {}

    # --- instruksi ---
    def LOAD_VALUE(self, number):
        self.stack.append(number)

    def ADD_TWO_VALUES(self):
        first_num = self.stack.pop()
        second_num = self.stack.pop()
        total = first_num + second_num
        self.stack.append(total)

    def PRINT_ANSWER(self):
        answer = self.stack.pop()
        print(answer)

    def STORE_NAME(self, name):
        val = self.stack.pop()
        self.environment[name] = val

    def LOAD_NAME(self, name):
        val = self.environment[name]
        self.stack.append(val)

    # --- mesin ---
    def parse_argument(self, instruction, argument, what_to_execute):
        """Pahami arti argumen tiap instruksi: indeks ke
        daftar numbers, atau indeks ke daftar names."""
        numbers = ["LOAD_VALUE"]
        names = ["LOAD_NAME", "STORE_NAME"]
        if instruction in numbers:
            argument = what_to_execute["numbers"][argument]
        elif instruction in names:
            argument = what_to_execute["names"][argument]
        return argument

    def execute(self, what_to_execute):
        instructions = what_to_execute["instructions"]
        for each_step in instructions:
            instruction, argument = each_step
            argument = self.parse_argument(instruction, argument,
                                           what_to_execute)
            bytecode_method = getattr(self, instruction)
            if argument is None:
                bytecode_method()
            else:
                bytecode_method(argument)
