# RENCANA — Build 18: Byterun (Interpreter Python di Python)

Panduan: Allison Kaptur, "A Python Interpreter Written
in Python", *500 Lines or Less* (AOSA) —
http://aosabook.org/en/500L/a-python-interpreter-written-in-python.html
Dibaca penuh sebelum mulai (20 Nov 2026). Seri buku yang
sama dengan build 9, 14, dan 17 seri ini.

## Peringatan ruang lingkup (dari babnya sendiri)

Catatan kaki bab: "based on bytecode produced by Python
3.5 or earlier". VM kita berjalan di Python 3.12.3, yang
bytecode-nya BERBEDA secara mekanis:

- wordcode: semua instruksi 2 byte (+ EXTENDED_ARG),
  lompatan dalam satuan instruksi, bukan byte;
- instruksi baru/berubah: RESUME, RETURN_CONST,
  BINARY_OP (satu instruksi utk semua operator, indeks
  tabel NB), PUSH_NULL + CALL (menggantikan
  CALL_FUNCTION), MAKE_FUNCTION dengan bit bendera,
  LOAD_GLOBAL dengan bit bendera null;
- SETUP_LOOP / SETUP_EXCEPT / SETUP_FINALLY HILANG:
  loop adalah lompatan murni; eksepsi memakai TABEL
  EKSEPSI (co_exceptiontable, zero-cost exceptions)
  dengan PUSH_EXC_INFO / CHECK_EXC_MATCH / RERAISE.

Jadi build ini: **arsitektur bab dipertahankan setia**
(VirtualMachine, Frame dengan data stack PER FRAME —
pelajaran bug generator babnya, Function pembungkus,
dispatch getattr byte_*, protokol why, Block), sedangkan
**penguraian & semantik instruksi mengikuti 3.12** untuk
korpus yang didefinisikan per irisan. Wasit tunggal:
CPython itu sendiri — setiap program korpus dijalankan
di kedua interpreter dan hasilnya (nilai kembali,
keluaran, tipe eksepsi) harus sama.

Di luar korpus (dinyatakan, tidak disembunyikan):
generator/yield, kelas & metaclass, import, kwargs &
*args pada CALL, comprehension (3.12 meng-inline-nya
dengan instruksi khusus), with, async. Bab cetaknya pun
tidak mengimplementasikan itu ("you'll quickly run into
instructions that this shorter version doesn't
implement") — pengecualian ini setia pada bab.

## Irisan

- [x] Irisan 1 — Interpreter mainan bab (bagian pertama):
  LOAD_VALUE / ADD_TWO_VALUES / PRINT_ANSWER atas dict
  {instructions, numbers}, lalu variabel (STORE_NAME /
  LOAD_NAME / parse_argument) dan dispatch getattr
  (execute). Jangkar bab: 7+5 -> 12; varian tiga nilai;
  a=1, b=2 -> cetak 3.
- [x] Irisan 2 — Inti VM atas bytecode 3.12 NYATA:
  Frame, VirtualMachine (make_frame/push/pop/run_frame),
  parse_byte_and_args wordcode (EXTENDED_ARG, CACHE
  dilewati, lompatan relatif satuan-instruksi),
  dispatch + why. Instruksi: RESUME, LOAD_CONST,
  RETURN_CONST, LOAD_FAST, STORE_FAST, LOAD_NAME,
  STORE_NAME, LOAD_GLOBAL, BINARY_OP, COMPARE_OP,
  UNARY_*, POP_TOP, lompatan (POP_JUMP_IF_*, JUMP_*).
  Korpus: cond() dan loop() dari bab (dikompilasi 3.12)
  + keluarga fungsi aritmetika/kondisional/while —
  diferensial vs CPython.
- [x] Irisan 3 — Fungsi & wadah: Function (getcallargs
  atas kembaran FunctionType asli), MAKE_FUNCTION
  bendera 3.12, PUSH_NULL + CALL, RETURN_VALUE;
  BUILD_LIST/TUPLE/MAP/SET, BINARY_SUBSCR, STORE_SUBSCR,
  LOAD_ATTR (bentuk polos), GET_ITER + FOR_ITER
  (for = lompatan murni), break/continue. Korpus:
  rekursi (fib, faktorial), argumen bawaan, contoh
  foo/bar bab, perulangan for, manipulasi list/dict.
- [x] Irisan 4 — Eksepsi gaya 3.12 + finale: tabel
  eksepsi diurai (dis._parse_exception_table sebagai
  pembanding), PUSH_EXC_INFO, CHECK_EXC_MATCH,
  POP_EXCEPT, RERAISE; korpus try/except bertipe,
  raise, eksepsi merambat antar frame, eksepsi tak
  tertangani keluar sebagai tipe yang sama dari
  run_code. Diferensial program acak terseed vs
  CPython. README + terbit.

## Pagar selesai

- [x] `uji_irisan1.py` … `uji_irisan4.py` semua hijau.
- [x] Setiap program korpus: hasil VM == hasil CPython
  (nilai, keluaran tercetak, tipe eksepsi).
- [x] `CATATAN.md` satu halaman per irisan: konsep inti + temuan.
- [x] Repo GitHub publik `build-your-own-byterun-python`
  terbit; blob SHA lokal == remote terverifikasi.
