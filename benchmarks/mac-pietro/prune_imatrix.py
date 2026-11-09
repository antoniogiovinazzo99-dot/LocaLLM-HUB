"""Ritaglia un imatrix di llama.cpp (formato GGUF) agli stessi K expert per layer scelti da prune_experts.py,
così si può riquantizzare un modello già potato. Uso: python -I prune_imatrix.py IMATRIX.gguf N_EXP K USCITA.gguf"""
import os, sys
import numpy as np
sys.path.insert(0, os.environ.get("GGUF_PY", "gguf-py"))  # cartella gguf-py di llama.cpp, oppure pip install gguf
import gguf  # noqa: E402
from gguf import GGUFReader, GGUFWriter, GGUFValueType  # noqa: E402

imx, n_exp, K, dst = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
im = GGUFReader(imx)
score = {}
for t in im.tensors:
    for kind in ("ffn_down_exps", "ffn_up_exps", "ffn_gate_exps"):
        if f".{kind}." in t.name and t.name.startswith("blk."):
            l = int(t.name.split(".")[1]); a = np.asarray(t.data, dtype=np.float64)
            if t.name.endswith(".counts"):
                if a.size >= n_exp: score.setdefault(l, {})["counts"] = a.reshape(-1)[:n_exp]
            elif t.name.endswith(".in_sum2") and a.size % n_exp == 0:
                score.setdefault(l, {})["sum2"] = a.reshape(n_exp, -1).sum(axis=1)
keep = {}
for l, s in score.items():
    order = np.lexsort((-s.get("sum2", np.zeros(n_exp)), -s["counts"]))
    keep[l] = np.sort(order[:K])
arch = im.fields["general.architecture"].contents() if "general.architecture" in im.fields else "imatrix"
w = GGUFWriter(dst, arch=arch)
for name, f in im.fields.items():
    if name.startswith("GGUF.") or name == "general.architecture":
        continue
    t0 = f.types[0]
    if t0 == GGUFValueType.ARRAY: w.add_key_value(name, f.contents(), t0, sub_type=f.types[-1])
    else: w.add_key_value(name, f.contents(), t0)
nt = 0
for t in im.tensors:
    data = np.asarray(t.data)
    if t.name.startswith("blk.") and "_exps." in t.name and data.ndim >= 1 and data.shape[0] == n_exp:
        l = int(t.name.split(".")[1])
        data = np.ascontiguousarray(data[keep[l]]); nt += 1
    w.add_tensor(t.name, data, raw_dtype=t.tensor_type)
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(progress=False); w.close()
print("ritagliati", nt, "tensori; scritto", dst)
