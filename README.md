# Build Your Own Byterun — Interpreter Python di Python

Implementasi ulang **Byterun** dari bab Allison Kaptur
di *500 Lines or Less* (AOSA): sebuah interpreter yang
menjalankan bytecode Python, ditulis dalam Python.

Bab aslinya menargetkan bytecode Python 3.5. Build ini
mempertahankan **arsitektur bab** — `VirtualMachine`,
`Frame` dengan tumpukan data per frame, `Function`,
dispatch `getattr` ke metode `byte_*` — dan menyesuaikan
**mekanik instruksinya ke Python 3.12**: wordcode,
`BINARY_OP`, `PUSH_NULL` + `CALL`, dan penanganan
eksepsi berbasis **tabel eksepsi** (zero-cost
exceptions) menggantikan `SETUP_EXCEPT`/tumpukan blok.
Setiap perilaku diverifikasi diferensial melawan
CPython itu sendiri. Lihat `CATATAN.md` untuk peta
adaptasinya dan `RENCANA.md` untuk ruang lingkupnya
(generator, kelas, import, kwargs, dan comprehension
berada di luar korpus — dinyatakan di sana).

## Isi

- `mainan.py` — interpreter mainan bab (mesin tumpukan
  atas dict instruksi), bagian pertama bab.
- `mesin.py` — VirtualMachine lengkap: Frame, Function,
  pengurai wordcode 3.12, ±45 instruksi, tabel eksepsi.
- `uji_irisan1.py` … `uji_irisan4.py` — baterai uji per
  irisan (total 31 pemeriksaan): jangkar bab, korpus
  fungsi bab yang dikompilasi 3.12, rekursi, wadah,
  try/except/finally, dan 300 program acak diferensial.

## Menjalankan uji

```bash
python3 uji_irisan1.py
python3 uji_irisan2.py
python3 uji_irisan3.py
python3 uji_irisan4.py
```

Hanya pustaka standar; butuh Python 3.12 (bytecode-nya
adalah target build ini).

## Atribusi

Struktur dan desain mengikuti bab "A Python
Interpreter Written in Python" oleh Allison Kaptur
(*500 Lines or Less*, AOSA Book,
http://aosabook.org/en/500L/a-python-interpreter-written-in-python.html),
diimplementasikan ulang sebagai latihan belajar dengan
adaptasi Python 3.12 seperti didokumentasikan di
`CATATAN.md`.
