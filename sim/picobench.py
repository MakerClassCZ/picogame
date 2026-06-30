# Sim shim for the native `picobench` module: lets examples/picobench_run.py RUN headless on the PC
# so the driver logic/formatting is validated. Timings are MEANINGLESS here (PC, no real kernels) -
# real numbers come only from a CIRCUITPY_PICOBENCH=1 firmware on the device.

_NAMES = [
    "A.div_c31", "A.recipmul31", "A.mod256", "A.and255", "A.mul32", "A.mul64",
    "A.clz", "A.bswap_builtin", "A.bswap_manual",
    "B.sinf", "B.sin_lut", "B.sqrtf", "B.rsqrt_fast", "B.isqrt", "B.fdiv", "B.fmul_recip",
    "B.q16mul", "B.fmul", "B.affine_float", "B.affine_q16",
    "C.memcpy_libc", "C.memcpy_word", "C.memset_libc", "C.fill_word",
    "C.byte_store", "C.word_store", "C.ram_sum",
    "D.blit565", "D.blit_pal8", "D.tint_recip", "D.pack444",
    "E.sum_os", "E.sum_o2", "E.unroll1", "E.unroll4", "E.dispatch_switch", "E.dispatch_ifladder",
    "F.hot_xip", "F.hot_ram",
]


def count():
    return len(_NAMES)


def name(i):
    return _NAMES[i]


def run(kid, iters):
    return kid          # no-op: real work + timing happen only on device


def info():
    return {"kernels": len(_NAMES), "ptr_bits": 64, "hw_float": True, "ram_xip_split": False}
