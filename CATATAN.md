# CATATAN — Byterun (Interpreter Python di Python)

Panduan: Allison Kaptur, "A Python Interpreter Written
in Python", *500 Lines or Less* (AOSA). Bab ditulis atas
bytecode Python 3.5; build ini mempertahankan arsitektur
bab dan menyesuaikan mekanik instruksinya ke Python
3.12.3 — wasit tunggalnya CPython sendiri.

## Irisan 1 — Interpreter mainan

Konsep inti bab sebelum bytecode sungguhan: mesin
tumpukan atas dict {instructions, numbers, names}.
Argumen instruksi adalah INDEKS (ke numbers / names)
yang diterjemahkan `parse_argument`; eksekusi memakai
dispatch `getattr` — pola yang sama persis yang kelak
dipakai VM sungguhan dengan awalan `byte_`. Jangkar bab
(7+5=12; a=1,b=2 -> 3) lolos apa adanya.

## Irisan 2 — Inti VM atas bytecode 3.12

Empat objek bab: VirtualMachine (tumpukan PANGGILAN),
Frame (code object, namespace, tumpukan DATA sendiri,
tumpukan blok), Function, Block. Pelajaran bug terkenal
bab — satu tumpukan data bersama mematahkan generator —
adalah alasan tumpukan data hidup per Frame.

Temuan adaptasi 3.5 -> 3.12:
- Wordcode: semua instruksi 2 byte; argumen lompatan
  RELATIF dalam satuan instruksi (bukan byte absolut).
- Lompatan dihitung dari akhir instruksi TERMASUK unit
  cache sejajarnya — terbukti dari FOR_ITER (1 cache):
  tanpa melewati cache, target meleset 2 byte dan loop
  berjalan ke JUMP_BACKWARD alih-alih END_FOR. Jumlah
  cache per opcode diambil dari `opcode._inline_cache_entries`.
- BINARY_ADD dkk dilebur menjadi BINARY_OP dengan
  indeks ke tabel NB (`dis._nb_ops`); indeks 13..25
  adalah varian di-tempat (+=, //=, ...).
- COMPARE_OP: indeks operator ada di bit tinggi oparg
  (`oparg >> 4`), urutan operatornya persis daftar bab.
- LOAD_GLOBAL: bit terendah oparg adalah bendera
  "dorong NULL dulu"; indeks nama = oparg >> 1 (berlaku
  juga untuk LOAD_ATTR).
- RETURN_CONST baru di 3.12; RESUME adalah no-op.

Dua penyimpangan sadar dari teks bab, keduanya dipaksa
wasit: (1) baris tercetak `make_frame` yang melebur
local_names ke global_names akan mematahkan rekursi —
di sini keduanya diteruskan apa adanya. (2) Frame akar
yang dibuat langsung untuk fungsi (tanpa modul) mengambil
__builtins__ dari modul mesin bila namespace lokal tak
menyediakannya.

## Irisan 3 — Fungsi & wadah

`Function.__call__` bab bekerja apa adanya di 3.12:
`inspect.getcallargs` atas kembaran `types.FunctionType`
memetakan argumen + nilai bawaan persis CPython, lalu
frame baru dibuat dan dijalankan. Yang berubah adalah
sekelilingnya: MAKE_FUNCTION 3.12 menaruh code object di
puncak dengan tuple defaults DI BAWAHNYA dan bit bendera
(0x01 defaults, 0x02 kwdefaults, 0x04 annotations,
0x08 closure) — bukan nama + code + defaults ala 3.5.
Pemanggilan menjadi PUSH_NULL + callable + argumen +
CALL; slot di bawah callable adalah NULL (atau penerima
dari LOAD_ATTR berbendera, yang menjadi argumen pertama —
semantik metode tak terikat).

Wadah: literal list konstan dikompilasi menjadi
BUILD_LIST 0 + LOAD_CONST tuple + LIST_EXTEND; literal
dict berkunci konstan memakai BUILD_CONST_KEY_MAP dengan
tuple kunci di PUNCAK tumpukan (bukan di bawah — tebakan
pertama gagal di wasit); STORE_SUBSCR membaca tumpukan
sebagai (nilai, objek, kunci). `__doc__` tidak bisa masuk
`__slots__` Function di Python 3 (bertabrakan dengan
docstring kelas) — ia hidup lewat `__dict__`.

## Irisan 4 — Eksepsi: tabel menggantikan blok

Di 3.5, try/except memakai SETUP_EXCEPT + tumpukan blok
+ protokol why bab. Di 3.12 semua itu hilang: kompiler
memancarkan TABEL EKSEPSI (`co_exceptiontable`, diurai
dengan `dis._parse_exception_table`) dan penangan adalah
kode biasa yang diawali PUSH_EXC_INFO. Mesin bab ternyata
sudah berbentuk tepat untuk ini: dispatch menangkap
eksepsi ke `last_exception` di dalam frame yang sedang
berjalan, jadi `run_frame` tinggal berkonsultasi ke
tabel pada offset instruksi yang gagal — truncate
tumpukan ke `depth` entri, dorong offset (bila `lasti`),
dorong nilai eksepsi, lompat ke `target`.

Tata letak tumpukan penangan diturunkan dari kendala
arus instruksinya, bukan ditebak: sesudah PUSH_EXC_INFO
tumpukan berisi [tipe, nilai, traceback, nilai] — tiga
slot pertama catatan untuk POP_EXCEPT, nilai di puncak
adalah salinan kerja. CHECK_EXC_MATCH hanya mem-pop
kelas penanding dan membaca nilai di puncak (isinstance),
sehingga nilai TETAP tersedia untuk klausul except
berikutnya (tebakan pertama — mem-pop tipe — gagal pada
klausul kedua). POP_EXCEPT di sini mengembalikan
tumpukan ke tinggi yang dicatat saat PUSH_EXC_INFO.
RERAISE melempar ulang instans yang sama; blok
pembersih kompiler (COPY 3; POP_EXCEPT; RERAISE 1)
berjalan benar di atas model ini.

Satu perbaikan dari bab: bab merekonstruksi eksepsi
dengan `exc(val)` saat menaikkannya kembali — itu
mengubah argumen eksepsi. Di sini instans aslinya yang
dinaikkan. Korpus finale: try/except bertipe, banyak
klausul, except-as, finally di kedua jalur, try
bersarang, raise antar frame, else — plus 300 program
acak terseed, 0 beda melawan CPython.
