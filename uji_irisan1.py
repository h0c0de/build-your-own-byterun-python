"""Uji Irisan 1 (Byterun) — interpreter mainan bab.

Jangkar bab persis: set instruksi 7 + 5 mencetak 12;
varian tiga nilai (7+5+8) mencetak 20; program variabel
a=1, b=2 mencetak 3; environment menyimpan nama; set
instruksi yang sama bisa dipakai ulang pada angka lain.
"""

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mainan import Interpreter

LULUS = 0


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


def jalankan(program):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        Interpreter().execute(program)
    return buf.getvalue()


program_bab = {
    "instructions": [("LOAD_VALUE", 0),
                     ("LOAD_VALUE", 1),
                     ("ADD_TWO_VALUES", None),
                     ("PRINT_ANSWER", None)],
    "numbers": [7, 5],
}
assert jalankan(program_bab) == "12\n"
ok("jangkar bab: 7 + 5 -> mencetak 12")

program_tiga = {
    "instructions": [("LOAD_VALUE", 0),
                     ("LOAD_VALUE", 1),
                     ("ADD_TWO_VALUES", None),
                     ("LOAD_VALUE", 2),
                     ("ADD_TWO_VALUES", None),
                     ("PRINT_ANSWER", None)],
    "numbers": [7, 5, 8],
}
assert jalankan(program_tiga) == "20\n"
ok("varian bab: (7 + 5) + 8 -> mencetak 20 (tumpukan melayani >2 nilai)")

program_var = {
    "instructions": [("LOAD_VALUE", 0),
                     ("STORE_NAME", 0),
                     ("LOAD_VALUE", 1),
                     ("STORE_NAME", 1),
                     ("LOAD_NAME", 0),
                     ("LOAD_NAME", 1),
                     ("ADD_TWO_VALUES", None),
                     ("PRINT_ANSWER", None)],
    "numbers": [1, 2],
    "names": ["a", "b"],
}
mesin = Interpreter()
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    mesin.execute(program_var)
assert buf.getvalue() == "3\n"
ok("program variabel bab: a=1, b=2 -> mencetak 3")
assert mesin.environment == {"a": 1, "b": 2}
ok("environment menyimpan pemetaan nama -> nilai")

program_umum = dict(program_bab, numbers=[40, 2])
assert jalankan(program_umum) == "42\n"
ok("set instruksi sama, numbers berbeda -> 42 (argumen = indeks, bukan nilai)")

mesin2 = Interpreter()
mesin2.LOAD_VALUE(9)
mesin2.LOAD_VALUE(1)
mesin2.ADD_TWO_VALUES()
assert mesin2.stack == [10]
ok("metode instruksi dapat dipanggil langsung; tumpukan berisi hasil")

print("\nIRISAN 1 HIJAU: %d pemeriksaan" % LULUS)
