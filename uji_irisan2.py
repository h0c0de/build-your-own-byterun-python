"""Uji Irisan 2 (Byterun) — inti VM atas bytecode 3.12 nyata.

Setiap program korpus dijalankan di VirtualMachine kita
DAN di CPython; nilai kembali harus sama persis. Program
korpus adalah fungsi-fungsi dari bab (cond, loop)
dikompilasi oleh Python 3.12 di sini, ditambah keluarga
aritmetika, kondisional, perulangan while, operator
unar, dan cuplikan level modul (LOAD_NAME/STORE_NAME).
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesin import VirtualMachine, VirtualMachineError

LULUS = 0


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


def panggil_vm(fungsi, *args):
    """Jalankan code object sebuah fungsi asli di VM,
    dengan callargs dibangun seperti Function bab
    (inspect.getcallargs atas fungsi aslinya)."""
    vm = VirtualMachine()
    callargs = inspect.getcallargs(fungsi, *args)
    bingkai = vm.make_frame(fungsi.__code__, callargs=callargs,
                            global_names=fungsi.__globals__,
                            local_names={})
    return vm.run_frame(bingkai)


def banding(fungsi, *kasus):
    for arg in kasus:
        arg = arg if isinstance(arg, tuple) else (arg,)
        harap = fungsi(*arg)
        dapat = panggil_vm(fungsi, *arg)
        assert dapat == harap, (fungsi.__name__, arg, harap, dapat)


# --- fungsi korpus ---
def cond(x):
    if x < 5:
        return 'yes'
    else:
        return 'no'


def loop(n):
    x = 1
    while x < n:
        x = x + 1
    return x


def hitung(a, b):
    return (a + b) * (a - b) // 2 % 7


def tanda(n):
    if n > 0:
        return -n if n % 2 == 0 else n
    elif n == 0:
        return 0
    return ~n


def jumlah_digit(n):
    total = 0
    while n > 0:
        total += n % 10
        n //= 10
    return total


def banding_teks(a, b):
    if a == b:
        return "sama"
    if a < b:
        return "kurang"
    return "lebih"


def logika(a, b):
    if a and not b:
        return 1
    if a or b:
        return 2
    return 3


banding(cond, 3, 5, 9, -2)
ok("cond() bab (dikompilasi 3.12) == CPython utk 4 masukan")

banding(loop, 5, 1, 0, 100)
ok("loop() bab (while + lompatan mundur) == CPython")

banding(hitung, (7, 5), (10, 3), (-4, 9), (0, 0))
ok("hitung(): BINARY_OP + - * // % == CPython")

banding(tanda, 4, 7, 0, -5)
ok("tanda(): unary - dan ~, elif, operator bersarang == CPython")

banding(jumlah_digit, 12345, 7, 1000000, 0)
ok("jumlah_digit(): += dan //= (BINARY_OP di-tempat) == CPython")

banding(banding_teks, ("apel", "apel"), ("apel", "jeruk"),
        ("zebra", "apel"))
ok("banding_teks(): COMPARE_OP == dan < pada str == CPython")

banding(logika, (True, False), (False, True), (False, False),
        (True, True))
ok("logika(): and/or/not lewat lompatan kondisional == CPython")

# --- level modul: LOAD_NAME / STORE_NAME / LOAD_GLOBAL ---
sumber = (
    "x = 3\n"
    "y = x * 2\n"
    "z = y > 5\n"
    "v = -y\n"
)
ruang = {"__builtins__": __builtins__}
vm = VirtualMachine()
vm.run_code(compile(sumber, "<uji>", "exec"),
            global_names=ruang, local_names=ruang)
assert ruang["x"] == 3 and ruang["y"] == 6
assert ruang["z"] is True and ruang["v"] == -6
ok("cuplikan modul: STORE_NAME/LOAD_NAME di namespace pemanggil")

# --- eksepsi sederhana sudah keluar sebagai tipe yang benar ---
def bagi_nol():
    return 1 / 0


try:
    panggil_vm(bagi_nol)
    raise AssertionError("harusnya ZeroDivisionError")
except ZeroDivisionError:
    ok("ZeroDivisionError di dalam VM keluar sebagai ZeroDivisionError")

# --- instruksi tak didukung dilaporkan jujur ---
# dispatch bab menangkap SEMUA eksepsi menjadi why='exception'
# + last_exception; lewat run_frame ia terbit lagi sebagai
# VirtualMachineError. Uji pada kedua permukaan itu.
vm2 = VirtualMachine()
why = vm2.dispatch("INSTRUMEN_PALSU", [])
assert why == "exception"
assert vm2.last_exception[0] is VirtualMachineError
ok("instruksi tak dikenal -> why='exception' + last_exception VirtualMachineError")

print("\nIRISAN 2 HIJAU: %d pemeriksaan" % LULUS)
