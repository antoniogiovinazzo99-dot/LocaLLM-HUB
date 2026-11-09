"""Potatura degli expert di un MoE GGUF (idea REAP, ICLR 2026), senza GPU e senza ri-quantizzare.
Tiene, in ogni layer, i K expert più usati secondo un imatrix di llama.cpp (conteggi per expert su un testo di calibrazione),
ritaglia i tensori *_exps e le righe del router, aggiorna expert_count. I pesi tenuti restano byte per byte identici.

Uso: python -I prune_experts.py MODELLO.gguf IMATRIX.gguf K USCITA.gguf
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.environ.get("GGUF_PY", "gguf-py"))  # cartella gguf-py di llama.cpp, oppure pip install gguf
import gguf  # noqa: E402
from gguf import GGUFReader, GGUFWriter, GGUFValueType  # noqa: E402

src, imx, K, dst = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
r = GGUFReader(src)
arch = r.fields["general.architecture"].contents()
n_exp = int(r.fields[f"{arch}.expert_count"].contents())
n_layer = int(r.fields[f"{arch}.block_count"].contents())
used = int(r.fields[f"{arch}.expert_used_count"].contents())
assert K >= used, "K deve essere almeno expert_used_count"

# importance per layer: imatrix counts (tokens routed to each expert) and, as tie-break, the summed squared activations
im = GGUFReader(imx)
score = {}
for t in im.tensors:
    for kind in ("ffn_down_exps", "ffn_up_exps", "ffn_gate_exps"):
        if f".{kind}." in t.name and t.name.startswith("blk."):
            l = int(t.name.split(".")[1])
            a = np.asarray(t.data, dtype=np.float64)
            if t.name.endswith(".counts"):
                v = a.reshape(-1)[:n_exp] if a.size >= n_exp else None
                if v is not None:
                    score.setdefault(l, {})["counts"] = v
            elif t.name.endswith(".in_sum2") and a.size % n_exp == 0:
                score.setdefault(l, {})["sum2"] = a.reshape(n_exp, -1).sum(axis=1)
keep = {}
for l in range(n_layer):
    s = score.get(l, {})
    c = s.get("counts")
    if c is None:
        raise SystemExit(f"imatrix senza conteggi per il layer {l}")
    tie = s.get("sum2", np.zeros(n_exp))
    order = np.lexsort((-tie, -c))   # by count desc, then activation desc
    keep[l] = np.sort(order[:K])
    print(f"layer {l}: tengo {K} expert, uso coperto {100 * c[keep[l]].sum() / max(1, c.sum()):.1f}%", flush=True)

w = GGUFWriter(dst, arch=arch)
for name, f in r.fields.items():
    if name.startswith("GGUF.") or name == "general.architecture":
        continue
    v = f.contents()
    if name == f"{arch}.expert_count":
        v = K
    t0 = f.types[0]
    if t0 == GGUFValueType.ARRAY:
        w.add_key_value(name, v, t0, sub_type=f.types[-1])
    else:
        w.add_key_value(name, v, t0)
w.add_string("general.pruned", f"REAP-style frequency pruning: {K} of {n_exp} experts per layer (imatrix counts)")
for t in r.tensors:
    data = t.data
    if t.name.startswith("blk.") and ("_exps." in t.name or t.name.endswith(".ffn_gate_inp.weight")):
        l = int(t.name.split(".")[1])
        data = np.ascontiguousarray(data[keep[l]])
    if t.tensor_type in (gguf.GGMLQuantizationType.F32, gguf.GGMLQuantizationType.F16):
        w.add_tensor(t.name, data, raw_dtype=t.tensor_type)
    else:
        w.add_tensor(t.name, np.asarray(data, dtype=np.uint8), raw_dtype=t.tensor_type)
w.write_header_to_file()
w.write_kv_data_to_file()
w.write_tensors_to_file(progress=False)
w.close()
print("scritto", dst, round(os.path.getsize(dst) / 1e9, 2), "GB")
