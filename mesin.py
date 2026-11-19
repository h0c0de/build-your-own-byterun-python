"""Byterun: interpreter Python yang ditulis di Python.

Arsitektur mengikuti bab Allison Kaptur (500 Lines or
Less): VirtualMachine memegang tumpukan PANGGILAN berisi
Frame; tiap Frame punya code object, namespace global/
lokal/builtin, tumpukan DATA sendiri, tumpukan blok, dan
penunjuk instruksi terakhir. Dispatch memakai getattr
ke metode byte_<NAMA>.

Semantik instruksinya mengikuti bytecode Python 3.12
(wordcode) — lihat RENCANA.md untuk peta adaptasinya
dari bytecode 3.5 yang dipakai bab.
"""


import collections
import dis
import inspect
import opcode as _opcode_mod
import operator
import sys
import types


class VirtualMachineError(Exception):
    pass


Block = collections.namedtuple("Block", "type, handler, stack_height")


class Frame:
    """Satu konteks eksekusi: code object + namespace +
    tumpukan data + tumpukan blok."""

    def __init__(self, code_obj, global_names, local_names, prev_frame):
        self.code_obj = code_obj
        self.global_names = global_names
        self.local_names = local_names
        self.prev_frame = prev_frame
        self.stack = []
        if prev_frame:
            self.builtin_names = prev_frame.builtin_names
        else:
            # frame akar: ambil dari namespace lokal; bila
            # frame fungsi dibuat langsung (tanpa modul),
            # pakai __builtins__ modul ini
            self.builtin_names = local_names.get('__builtins__',
                                                 __builtins__)
            if hasattr(self.builtin_names, '__dict__'):
                self.builtin_names = self.builtin_names.__dict__
        self.last_instruction = 0
        self.block_stack = []
        self.offset_ini = 0      # offset instruksi yang sedang jalan
        self.exc_bases = []      # tinggi tumpukan pra-PUSH_EXC_INFO

    # nama-nama yang dipakai metode byte_* (seperti bab)
    @property
    def f_locals(self):
        return self.local_names

    @property
    def f_globals(self):
        return self.global_names

    @property
    def f_builtins(self):
        return self.builtin_names


class VirtualMachine:
    def __init__(self):
        self.frames = []        # tumpukan panggilan
        self.frame = None       # frame saat ini
        self.return_value = None
        self.last_exception = None
        self._oparg_mentah = 0  # oparg instruksi terakhir (utk bit bendera)
        self._tabel_cache = {}  # id(code) -> entri tabel eksepsi

    # ---------- titik masuk ----------
    def run_code(self, code, global_names=None, local_names=None):
        """Jalankan sebuah code object sampai tuntas."""
        frame = self.make_frame(code, global_names=global_names,
                                local_names=local_names)
        return self.run_frame(frame)

    # ---------- manipulasi frame ----------
    def make_frame(self, code, callargs=None, global_names=None,
                   local_names=None):
        if callargs is None:
            callargs = {}
        if global_names is not None and local_names is not None:
            # keduanya diberikan pemanggil: pakai apa adanya.
            # (Baris tercetak bab melebur local ke global;
            # itu mematahkan rekursi — lihat CATATAN.)
            pass
        elif self.frames:
            global_names = self.frame.global_names
            local_names = {}
        else:
            global_names = local_names = {
                '__builtins__': __builtins__,
                '__name__': '__main__',
                '__doc__': None,
                '__package__': None,
            }
        local_names.update(callargs)
        frame = Frame(code, global_names, local_names, self.frame)
        return frame

    def push_frame(self, frame):
        self.frames.append(frame)
        self.frame = frame

    def pop_frame(self):
        self.frames.pop()
        if self.frames:
            self.frame = self.frames[-1]
        else:
            self.frame = None

    # ---------- manipulasi tumpukan data ----------
    def top(self):
        return self.frame.stack[-1]

    def pop(self):
        return self.frame.stack.pop()

    def push(self, *vals):
        self.frame.stack.extend(vals)

    def popn(self, n):
        """Pop n nilai; kembalikan list, yang terdalam dulu."""
        if n:
            ret = self.frame.stack[-n:]
            self.frame.stack[-n:] = []
            return ret
        else:
            return []

    def jump(self, jump):
        self.frame.last_instruction = jump

    # ---------- penguraian bytecode (wordcode 3.12) ----------
    def parse_byte_and_args(self):
        f = self.frame
        code = f.code_obj.co_code
        opoffset = f.last_instruction
        opcode = code[opoffset]
        oparg = code[opoffset + 1]
        f.last_instruction += 2
        # EXTENDED_ARG: oparg sesungguhnya disambung dari
        # unit-unit berikutnya
        while opcode == dis.EXTENDED_ARG:
            opcode = code[f.last_instruction]
            oparg = (oparg << 8) | code[f.last_instruction + 1]
            f.last_instruction += 2
        byte_name = dis.opname[opcode]
        self._oparg_mentah = oparg
        f.offset_ini = opoffset
        # Lewati unit-unit cache sejajar milik instruksi ini:
        # target lompatan relatif 3.12 dihitung dari AKHIR
        # instruksi TERMASUK cache-nya (kasus FOR_ITER).
        f.last_instruction += 2 * _opcode_mod._inline_cache_entries[opcode]

        if opcode >= dis.HAVE_ARGUMENT:
            if opcode in dis.hasconst:
                arg = f.code_obj.co_consts[oparg]
            elif opcode in dis.hasname:
                if byte_name in ("LOAD_GLOBAL", "STORE_GLOBAL",
                                 "LOAD_ATTR", "STORE_ATTR"):
                    # 3.12: bit terendah oparg adalah bendera,
                    # indeks nama digeser satu bit
                    arg = f.code_obj.co_names[oparg >> 1]
                else:
                    arg = f.code_obj.co_names[oparg]
            elif opcode in dis.haslocal:
                arg = f.code_obj.co_varnames[oparg]
            elif opcode in dis.hasjrel:
                # lompatan relatif, dalam satuan instruksi (2 byte)
                if "BACKWARD" in byte_name:
                    arg = f.last_instruction - oparg * 2
                else:
                    arg = f.last_instruction + oparg * 2
            elif byte_name == "COMPARE_OP":
                # 3.12: indeks operator di bit tinggi oparg
                arg = oparg >> 4
            else:
                arg = oparg
            argument = [arg]
        else:
            argument = []
        return byte_name, argument

    # ---------- dispatch ----------
    def dispatch(self, byte_name, argument):
        """Jalankan satu instruksi; tangkap eksepsinya ke
        last_exception dan laporkan lewat why."""
        why = None
        try:
            bytecode_fn = getattr(self, 'byte_%s' % byte_name, None)
            if bytecode_fn is None:
                if byte_name == "CACHE":
                    pass  # unit cache sejajar: tak ada artinya
                elif byte_name.startswith('UNARY_'):
                    self.unaryOperator(byte_name[6:])
                elif byte_name.startswith('BINARY_'):
                    self.binaryOperator(byte_name[7:])
                else:
                    raise VirtualMachineError(
                        "unsupported bytecode type: %s" % byte_name)
            else:
                why = bytecode_fn(*argument)
        except Exception:
            self.last_exception = sys.exc_info()[:2] + (None,)
            why = 'exception'
        return why

    def run_frame(self, frame):
        """Jalankan frame sampai ia kembali (bagaimanapun
        caranya). Eksepsi dinaikkan, nilai kembali dikembalikan."""
        self.push_frame(frame)
        while True:
            byte_name, arguments = self.parse_byte_and_args()
            why = self.dispatch(byte_name, arguments)

            if why == 'exception':
                # 3.12: cari penangan di TABEL EKSEPSI frame
                # untuk offset instruksi yang gagal
                entri = self._cari_penangan(frame)
                if entri is not None:
                    del frame.stack[entri.depth:]
                    if entri.lasti:
                        self.push(frame.offset_ini)
                    self.push(self.last_exception[1])
                    self.jump(entri.target)
                    continue

            while why and frame.block_stack:
                why = self.manage_block_stack(why)

            if why:
                break

        self.pop_frame()

        if why == 'exception':
            # naikkan INSTANS aslinya (bab merekonstruksi
            # exc(val) — itu mengubah argumen eksepsi)
            raise self.last_exception[1]
        return self.return_value

    # ---------- tabel eksepsi (zero-cost exceptions 3.11+) ----------
    def _cari_penangan(self, frame):
        """Entri tabel eksepsi yang mencakup offset instruksi
        yang baru gagal di frame ini, atau None."""
        kode = frame.code_obj
        tabel = self._tabel_cache.get(id(kode))
        if tabel is None:
            tabel = list(dis._parse_exception_table(kode))
            self._tabel_cache[id(kode)] = tabel
        for entri in tabel:
            if entri.start <= frame.offset_ini < entri.end:
                return entri
        return None

    # ---------- manipulasi tumpukan blok ----------
    def push_block(self, b_type, handler=None):
        stack_height = len(self.frame.stack)
        self.frame.block_stack.append(Block(b_type, handler, stack_height))

    def pop_block(self):
        return self.frame.block_stack.pop()

    def unwind_block(self, block):
        """Bongkar nilai di tumpukan data milik sebuah blok."""
        if block.type == 'except-handler':
            offset = 3
        else:
            offset = 0
        while len(self.frame.stack) > block.stack_height + offset:
            self.pop()
        if block.type == 'except-handler':
            traceback, value, exctype = self.popn(3)
            self.last_exception = exctype, value, traceback

    def manage_block_stack(self, why):
        frame = self.frame
        block = frame.block_stack[-1]
        if block.type == 'loop' and why == 'continue':
            self.jump(self.return_value)
            why = None
            return why

        self.pop_block()
        self.unwind_block(block)

        if block.type == 'loop' and why == 'break':
            why = None
            self.jump(block.handler)
            return why

        if (block.type in ['setup-except', 'finally']
                and why == 'exception'):
            self.push_block('except-handler')
            exctype, value, tb = self.last_exception
            self.push(tb, value, exctype)
            self.push(tb, value, exctype)  # ya, dua kali
            why = None
            self.jump(block.handler)
            return why

        elif block.type == 'finally':
            if why in ('return', 'continue'):
                self.push(self.return_value)
                self.push(why)
            why = None
            self.jump(block.handler)
            return why

        return why

    # ---------- instruksi: tumpukan & konstanta ----------
    def byte_LOAD_CONST(self, const):
        self.push(const)

    def byte_RETURN_CONST(self, const):
        self.return_value = const
        return "return"

    def byte_RETURN_VALUE(self):
        self.return_value = self.pop()
        return "return"

    def byte_POP_TOP(self):
        self.pop()

    def byte_RESUME(self, arg):
        pass

    # ---------- instruksi: nama ----------
    def byte_LOAD_NAME(self, name):
        frame = self.frame
        if name in frame.f_locals:
            val = frame.f_locals[name]
        elif name in frame.f_globals:
            val = frame.f_globals[name]
        elif name in frame.f_builtins:
            val = frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_STORE_NAME(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_FAST(self, name):
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        else:
            raise UnboundLocalError(
                "local variable '%s' referenced before assignment" % name)
        self.push(val)

    def byte_STORE_FAST(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_GLOBAL(self, name):
        f = self.frame
        if name in f.f_globals:
            val = f.f_globals[name]
        elif name in f.f_builtins:
            val = f.f_builtins[name]
        else:
            raise NameError("global name '%s' is not defined" % name)
        # bendera oparg 3.12: bit 0 -> dorong NULL sebelum nilai
        # (persiapan pola pemanggilan)
        if self._oparg_mentah & 1:
            self.push(None)
        self.push(val)

    def byte_STORE_GLOBAL(self, name):
        self.frame.f_globals[name] = self.pop()

    # ---------- instruksi: operator ----------
    # Tabel NB 3.12 (dis._nb_ops): indeks -> operator.
    # Indeks 13..25 adalah varian di-tempat (+=, dst.) yang
    # secara nilai sama dengan bentuk biasanya.
    _NB_SIMBOL = ['+', '&', '//', '<<', '@', '*', '%', '|',
                  '**', '>>', '-', '/', '^']
    _NB_FUNGSI = {
        '+': operator.add, '&': operator.and_,
        '//': operator.floordiv, '<<': operator.lshift,
        '@': operator.matmul, '*': operator.mul,
        '%': operator.mod, '|': operator.or_,
        '**': operator.pow, '>>': operator.rshift,
        '-': operator.sub, '/': operator.truediv,
        '^': operator.xor,
    }

    def byte_BINARY_OP(self, opnum):
        if opnum >= 13:
            opnum -= 13  # varian di-tempat: nilai sama
        x, y = self.popn(2)
        self.push(self._NB_FUNGSI[self._NB_SIMBOL[opnum]](x, y))

    BINARY_OPERATORS = {
        'POWER': pow,
        'MULTIPLY': operator.mul,
        'FLOOR_DIVIDE': operator.floordiv,
        'TRUE_DIVIDE': operator.truediv,
        'MODULO': operator.mod,
        'ADD': operator.add,
        'SUBTRACT': operator.sub,
        'SUBSCR': operator.getitem,
        'LSHIFT': operator.lshift,
        'RSHIFT': operator.rshift,
        'AND': operator.and_,
        'XOR': operator.xor,
        'OR': operator.or_,
    }

    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(self.BINARY_OPERATORS[op](x, y))

    UNARY_OPERATORS = {
        'POSITIVE': operator.pos,
        'NEGATIVE': operator.neg,
        'NOT': operator.not_,
        'INVERT': operator.invert,
    }

    def unaryOperator(self, op):
        x = self.pop()
        self.push(self.UNARY_OPERATORS[op](x))

    COMPARE_OPERATORS = [
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    ]

    def byte_COMPARE_OP(self, opnum):
        x, y = self.popn(2)
        self.push(self.COMPARE_OPERATORS[opnum](x, y))

    # ---------- instruksi: lompatan ----------
    def byte_JUMP_FORWARD(self, jump):
        self.jump(jump)

    def byte_JUMP_BACKWARD(self, jump):
        self.jump(jump)

    def byte_JUMP_ABSOLUTE(self, jump):
        self.jump(jump)

    def byte_POP_JUMP_IF_TRUE(self, jump):
        val = self.pop()
        if val:
            self.jump(jump)

    def byte_POP_JUMP_IF_FALSE(self, jump):
        val = self.pop()
        if not val:
            self.jump(jump)

    # ---------- instruksi: fungsi & pemanggilan (3.12) ----------
    def byte_PUSH_NULL(self):
        self.push(None)

    def byte_MAKE_FUNCTION(self, flags):
        # 3.12: code object di puncak; di bawahnya, sesuai
        # bit bendera: closure (0x08), annotations (0x04),
        # kwdefaults (0x02), defaults (0x01).
        code = self.pop()
        closure = None
        kwdefaults = None
        defaults = ()
        if flags & 0x08:
            closure = self.pop()
        if flags & 0x04:
            self.pop()  # annotations: tak dipakai VM ini
        if flags & 0x02:
            kwdefaults = self.pop()
        if flags & 0x01:
            defaults = self.pop()
        globs = self.frame.f_globals
        fn = Function(code.co_name, code, globs, defaults,
                      closure, self, kwdefaults)
        self.push(fn)

    def byte_CALL(self, argc):
        # tumpukan: [NULL/self, callable, arg1..argN]
        args = self.popn(argc)
        func = self.pop()
        slot = self.pop()
        if slot is not None:
            # penerima dari LOAD_ATTR berbendera: ia menjadi
            # argumen pertama (semantik metode tak-terikat)
            args = [slot] + args
        retval = func(*args)
        self.push(retval)

    # ---------- instruksi: atribut & subskrip ----------
    def byte_LOAD_ATTR(self, name):
        obj = self.pop()
        val = getattr(obj, name)
        if self._oparg_mentah & 1:
            # bentuk pemanggilan metode 3.12: metode terikat
            # didahului NULL; atribut biasa didahului objeknya
            if hasattr(val, '__self__'):
                self.push(None)
            else:
                self.push(obj)
        self.push(val)

    def byte_STORE_ATTR(self, name):
        val, obj = self.popn(2)
        setattr(obj, name, val)

    def byte_STORE_SUBSCR(self):
        # tumpukan (terdalam->puncak): nilai, objek, kunci
        val, obj, key = self.popn(3)
        obj[key] = val

    # ---------- instruksi: membangun wadah ----------
    def byte_BUILD_LIST(self, count):
        elts = self.popn(count)
        self.push(elts)

    def byte_BUILD_TUPLE(self, count):
        elts = self.popn(count)
        self.push(tuple(elts))

    def byte_BUILD_SET(self, count):
        elts = self.popn(count)
        self.push(set(elts))

    def byte_BUILD_MAP(self, count):
        # 3.12: tumpukan berisi count pasang kunci/nilai
        elts = self.popn(2 * count)
        peta = {}
        for i in range(count):
            peta[elts[2 * i]] = elts[2 * i + 1]
        self.push(peta)

    def byte_BUILD_CONST_KEY_MAP(self, count):
        # literal dict berkunci konstan: nilai-nilai dulu,
        # tuple kunci di PUNCAK tumpukan
        elts = self.popn(count + 1)
        kunci = elts[-1]
        self.push(dict(zip(kunci, elts[:-1])))

    def byte_LIST_EXTEND(self, count):
        iterable = self.pop()
        the_list = self.frame.stack[-count]
        the_list.extend(iterable)

    def byte_LIST_APPEND(self, count):
        val = self.pop()
        the_list = self.frame.stack[-count]  # intip, jangan pop
        the_list.append(val)

    def byte_SET_UPDATE(self, count):
        iterable = self.pop()
        the_set = self.frame.stack[-count]
        the_set.update(iterable)

    # ---------- instruksi: iterasi ----------
    def byte_GET_ITER(self):
        self.push(iter(self.pop()))

    def byte_FOR_ITER(self, jump):
        iterobj = self.top()
        try:
            v = next(iterobj)
            self.push(v)
        except StopIteration:
            self.pop()
            self.jump(jump)

    def byte_END_FOR(self):
        pass  # penanda akhir loop 3.12; iterator sudah di-pop FOR_ITER

    # ---------- instruksi: eksepsi (tabel 3.12) ----------
    def byte_NOP(self):
        pass

    def byte_PUSH_EXC_INFO(self):
        # tumpukan masuk: [..., nilai_eksepsi]; keluar:
        # [..., tipe, nilai, traceback, nilai] — tiga slot
        # pertama adalah catatan eksepsi utk POP_EXCEPT;
        # nilai di puncak adalah salinan kerja yang dibaca
        # CHECK_EXC_MATCH dan diambil POP_TOP / STORE_FAST.
        frame = self.frame
        frame.exc_bases.append(len(frame.stack) - 1)
        typ, val, tb = self.last_exception
        frame.stack[-1:-1] = [typ, val, tb]

    def byte_CHECK_EXC_MATCH(self):
        # kelas penanding di puncak; di bawahnya nilai
        # eksepsi. Kelasnya di-pop, hasilnya (bool) di-push;
        # nilai eksepsi TETAP untuk klausul except berikutnya.
        cls = self.pop()
        val = self.top()
        self.push(isinstance(val, cls))

    def byte_POP_EXCEPT(self):
        # kembalikan tumpukan ke tinggi sebelum PUSH_EXC_INFO
        frame = self.frame
        if frame.exc_bases:
            dasar = frame.exc_bases.pop()
            del frame.stack[dasar:]

    def byte_RERAISE(self, oparg):
        # lempar ulang eksepsi yang sedang ditangani;
        # dispatch menangkapnya dan tabel eksepsi yang
        # memutuskan langkah berikutnya
        raise self.last_exception[1]

    def byte_RAISE_VARARGS(self, argc):
        if argc == 0:
            raise self.last_exception[1]
        elif argc == 1:
            exc = self.pop()
            if isinstance(exc, type) and issubclass(exc, BaseException):
                raise exc()
            raise exc
        elif argc == 2:
            penyebab = self.pop()
            exc = self.pop()
            if isinstance(exc, type) and issubclass(exc, BaseException):
                exc = exc()
            exc.__cause__ = penyebab
            raise exc

    def byte_COPY(self, i):
        self.push(self.frame.stack[-i])

    def byte_SWAP(self, i):
        tumpukan = self.frame.stack
        tumpukan[-1], tumpukan[-i] = tumpukan[-i], tumpukan[-1]

    def byte_DELETE_FAST(self, name):
        del self.frame.f_locals[name]


def make_cell(value):
    """Buat closure Python asli dan ambil cell-nya."""
    fn = (lambda x: lambda: x)(value)
    return fn.__closure__[0]


class Function:
    """Bungkus fungsi yang bisa dipanggil VM: memanggilnya
    berarti membuat Frame baru dan menjalankannya. Kembaran
    FunctionType asli dipakai agar inspect.getcallargs bisa
    memetakan argumen (termasuk nilai bawaan) persis CPython.
    """

    # '__doc__' TIDAK masuk __slots__: di Python 3 ia
    # bertabrakan dengan docstring kelas (ValueError).
    # Bab mencantumkannya; di sini ia hidup lewat __dict__.
    __slots__ = [
        'func_code', 'func_name', 'func_defaults', 'func_globals',
        'func_locals', 'func_dict', 'func_closure',
        '__name__', '__dict__',
        '_vm', '_func',
        'func_kwdefaults',
    ]

    def __init__(self, name, code, globs, defaults, closure, vm,
                 kwdefaults=None):
        self._vm = vm
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_defaults = tuple(defaults)
        self.func_globals = globs
        self.func_locals = vm.frame.f_locals
        self.__dict__ = {}
        self.func_closure = closure
        self.__doc__ = code.co_consts[0] if code.co_consts else None
        self.func_kwdefaults = kwdefaults
        # kadang kita butuh fungsi Python asli; ini untuk itu
        kw = {'argdefs': self.func_defaults}
        if kwdefaults:
            kw['kwdefaults'] = kwdefaults
        if closure:
            kw['closure'] = tuple(make_cell(0) for _ in closure)
        self._func = types.FunctionType(code, globs, **kw)

    def __call__(self, *args, **kwargs):
        """Saat Function dipanggil, buat frame baru dan jalankan."""
        callargs = inspect.getcallargs(self._func, *args, **kwargs)
        frame = self._vm.make_frame(
            self.func_code, callargs, self.func_globals, {})
        return self._vm.run_frame(frame)

    def byte_JUMP_IF_TRUE_OR_POP(self, jump):
        val = self.top()
        if val:
            self.jump(jump)
        else:
            self.pop()

    def byte_JUMP_IF_FALSE_OR_POP(self, jump):
        val = self.top()
        if not val:
            self.jump(jump)
        else:
            self.pop()
