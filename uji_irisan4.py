"""Uji Irisan 4 (Byterun) — eksepsi gaya 3.12 + finale.

Korpus try/except/finally/raise dijalankan sebagai modul
di VM dan di CPython; namespace DAN keluaran DAN tipe
eksepsi yang lolos harus sama. Ditutup diferensial
program acak terseed (fungsi aritmetika/kontrol/eksepsi
yang dibangkitkan prosedural) dan regresi irisan 1-3.
"""

import contextlib
import io
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mesin import VirtualMachine

LULUS = 0


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


def jalankan(sumber, mesin):
    """Jalankan sumber; kembalikan (namespace, keluaran,
    tipe eksepsi yang lolos atau None)."""
    if mesin == "vm":
        ruang = {"__builtins__": __builtins__}
        vm = VirtualMachine()
        buf = io.StringIO()
        galat = None
        with contextlib.redirect_stdout(buf):
            try:
                vm.run_code(compile(sumber, "<uji>", "exec"),
                            global_names=ruang, local_names=ruang)
            except BaseException as e:
                galat = type(e).__name__
        return ruang, buf.getvalue(), galat
    else:
        ruang = {"__builtins__": __builtins__}
        buf = io.StringIO()
        galat = None
        with contextlib.redirect_stdout(buf):
            try:
                exec(compile(sumber, "<uji>", "exec"), ruang)
            except BaseException as e:
                galat = type(e).__name__
        return ruang, buf.getvalue(), galat


def sama(sumber, *nama_variabel):
    vm_ns, vm_out, vm_err = jalankan(sumber, "vm")
    as_ns, as_out, as_err = jalankan(sumber, "asli")
    for nama in nama_variabel:
        assert vm_ns.get(nama) == as_ns.get(nama), \
            (nama, vm_ns.get(nama), as_ns.get(nama))
    assert vm_out == as_out, (vm_out, as_out)
    assert vm_err == as_err, (vm_err, as_err)
    return vm_ns, vm_err


SRC_DASAR = """
def aman(x):
    try:
        return 10 // x
    except ZeroDivisionError:
        return -1

def dua(x):
    try:
        return [1, 2][x]
    except IndexError:
        return "indeks"
    except Exception:
        return "lain"

a = aman(0)
b = aman(3)
c = dua(5)
d = dua(0)
e = dua("teks")
"""
ns, _ = sama(SRC_DASAR, "a", "b", "c", "d", "e")
assert (ns["a"], ns["b"], ns["c"], ns["d"], ns["e"]) == \
    (-1, 3, "indeks", 1, "lain")
ok("try/except bertipe + dua klausul except + except Exception == CPython")

SRC_RAISE = """
def lempar(x):
    if x < 0:
        raise ValueError("negatif")
    return x

def bungkus(x):
    try:
        return lempar(x)
    except ValueError:
        return "tertangkap"

p = bungkus(5)
q = bungkus(-3)
"""
ns, _ = sama(SRC_RAISE, "p", "q")
assert (ns["p"], ns["q"]) == (5, "tertangkap")
ok("raise di frame dalam, tertangkap di frame luar == CPython")

SRC_LOLOS = """
def lempar(x):
    if x < 0:
        raise ValueError("negatif")
    return x

r = lempar(-1)
"""
_, err = sama(SRC_LOLOS)
assert err == "ValueError"
ok("eksepsi tak tertangani lolos sebagai tipe yang sama (ValueError)")

SRC_AS_FINALLY = """
def dengan_finally(x):
    hasil = []
    try:
        hasil.append(10 // x)
    except ZeroDivisionError as e:
        hasil.append("galat")
    finally:
        hasil.append("selesai")
    return hasil

f0 = dengan_finally(0)
f2 = dengan_finally(2)

def bersarang(x):
    try:
        try:
            return 1 // x
        except ZeroDivisionError:
            raise ValueError("dari dalam")
    except ValueError:
        return "tertangkap luar"

s0 = bersarang(0)
s1 = bersarang(1)
"""
ns, _ = sama(SRC_AS_FINALLY, "f0", "f2", "s0", "s1")
assert ns["f0"] == ["galat", "selesai"]
assert ns["f2"] == [5, "selesai"]
assert ns["s0"] == "tertangkap luar" and ns["s1"] == 1
ok("except ... as, finally (kedua jalur), try bersarang + raise ulang == CPython")

SRC_ELSE = """
def coba(x):
    try:
        y = 10 // x
    except ZeroDivisionError:
        return "gagal"
    else:
        return y + 1

u = coba(2)
v = coba(0)
"""
ns, _ = sama(SRC_ELSE, "u", "v")
assert (ns["u"], ns["v"]) == (6, "gagal")
ok("try/except/else == CPython")

# --- diferensial acak terseed ---
def bangkit_program(rng):
    """Satu fungsi acak: aritmetika, kondisional, loop,
    dan kemungkinan raise yang tertangkap."""
    a = rng.randint(-9, 9)
    b = rng.randint(1, 9)
    c = rng.randint(0, 20)
    return f"""
def f(x):
    total = x + {a}
    for i in range({c % 5}):
        total += i * {b}
    if total % 3 == 0:
        total //= 3
    try:
        total += 100 // (x - {a})
    except ZeroDivisionError:
        total -= 7
    while total > 50:
        total -= 13
    return total

hasil = f({rng.randint(-5, 15)})
"""


rng = random.Random(20261120)
cocok = 0
for i in range(300):
    sumber = bangkit_program(rng)
    vm_ns, _, vm_err = jalankan(sumber, "vm")
    as_ns, _, as_err = jalankan(sumber, "asli")
    assert vm_err == as_err and vm_ns["hasil"] == as_ns["hasil"], \
        (sumber, vm_ns.get("hasil"), as_ns.get("hasil"))
    cocok += 1
assert cocok == 300
ok("diferensial acak terseed: 300 program, 0 beda vs CPython")

print("== regresi irisan 1-3 ==")
for n in (1, 2, 3):
    r = subprocess.run([sys.executable, "uji_irisan%d.py" % n],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    ok("uji_irisan%d hijau penuh" % n)

print("\nIRISAN 4 HIJAU: %d pemeriksaan" % LULUS)
