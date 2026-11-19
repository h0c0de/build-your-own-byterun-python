"""Uji Irisan 3 (Byterun) — fungsi & wadah gaya 3.12.

Seluruh program sumber dijalankan sebagai code object
MODUL di VirtualMachine dan di CPython (exec); namespace
akhir harus sama. Mencakup MAKE_FUNCTION + nilai bawaan,
rekursi lewat LOAD_GLOBAL berbendera, PUSH_NULL + CALL,
pemanggilan metode (list.append), BUILD_LIST/MAP +
LIST_EXTEND, BINARY_SUBSCR/STORE_SUBSCR, dan for lewat
GET_ITER/FOR_ITER.
"""

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesin import VirtualMachine

LULUS = 0


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


def jalankan_keduanya(sumber):
    """Kembalikan (namespace VM, namespace CPython, keluaran VM,
    keluaran CPython) untuk satu program sumber."""
    ruang_vm = {"__builtins__": __builtins__}
    vm = VirtualMachine()
    buf_vm = io.StringIO()
    with contextlib.redirect_stdout(buf_vm):
        vm.run_code(compile(sumber, "<uji>", "exec"),
                    global_names=ruang_vm, local_names=ruang_vm)
    ruang_asli = {"__builtins__": __builtins__}
    buf_asli = io.StringIO()
    with contextlib.redirect_stdout(buf_asli):
        exec(compile(sumber, "<uji>", "exec"), ruang_asli)
    return ruang_vm, ruang_asli, buf_vm.getvalue(), buf_asli.getvalue()


def sama(sumber, *nama_variabel):
    vm_ns, asli_ns, out_vm, out_asli = jalankan_keduanya(sumber)
    for nama in nama_variabel:
        assert vm_ns[nama] == asli_ns[nama], \
            (nama, vm_ns.get(nama), asli_ns.get(nama))
    assert out_vm == out_asli, (out_vm, out_asli)
    return vm_ns


SRC_FUNGSI = """
def tambah(a, b=10):
    return a + b

def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def faktorial(n):
    hasil = 1
    while n > 1:
        hasil *= n
        n -= 1
    return hasil

a1 = tambah(5)
a2 = tambah(5, 7)
f10 = fib(10)
f12 = faktorial(12)
"""
ns = sama(SRC_FUNGSI, "a1", "a2", "f10", "f12")
assert (ns["a1"], ns["a2"], ns["f10"], ns["f12"]) == (15, 12, 55, 479001600)
ok("fungsi + bawaan + rekursi fib(10)=55 + faktorial == CPython")

SRC_WADAH = """
lst = [1, 2, 3]
lst.append(4)
lst2 = [lst[0], lst[-1]]
d = {'a': lst[0], 'b': 99}
d['c'] = d['a'] + d['b']
t = (len(lst), sum(lst))
s = {1, 2, 2, 3}
gabung = []
for v in lst:
    gabung.append(v * 10)
total = 0
for v in lst:
    total += v
teks = "halo"
per_huruf = []
for h in teks:
    per_huruf.append(h.upper())
"""
ns = sama(SRC_WADAH, "lst", "lst2", "d", "t", "s", "gabung",
          "total", "per_huruf")
assert ns["d"] == {'a': 1, 'b': 99, 'c': 100}
assert ns["gabung"] == [10, 20, 30, 40] and ns["total"] == 10
ok("list/dict/set/tuple, append, subskrip, for atas list & str == CPython")

SRC_CETAK = """
def sapa(nama):
    return "halo " + nama

for i in range(3):
    print(sapa("dunia"), i)

daftar = []
for n in range(10):
    if n % 2 == 0:
        continue
    if n > 7:
        break
    daftar.append(n)
print(daftar)
"""
ns = sama(SRC_CETAK, "daftar")
assert ns["daftar"] == [1, 3, 5, 7]
ok("print dari dalam VM, range, continue & break == CPython (termasuk keluaran)")

SRC_SALING = """
def genap(n):
    if n == 0:
        return True
    return ganjil(n - 1)

def ganjil(n):
    if n == 0:
        return False
    return genap(n - 1)

g10 = genap(10)
g7 = genap(7)
"""
ns = sama(SRC_SALING, "g10", "g7")
assert ns["g10"] is True and ns["g7"] is False
ok("rekursi saling (mutual recursion) dua fungsi == CPython")

print("== regresi irisan 1-2 ==")
import subprocess
for n in (1, 2):
    r = subprocess.run([sys.executable, "uji_irisan%d.py" % n],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    ok("uji_irisan%d hijau penuh" % n)

print("\nIRISAN 3 HIJAU: %d pemeriksaan" % LULUS)
