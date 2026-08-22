"""Diagnostic for the G-2 artifact: fiber sizes, value-relevance, witnesses."""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
if len(sys.argv) > 2 and sys.argv[2] == "full":
    d["per_surface"] = d["per_surface_full_value_delta"]
print("contrast:", d["per_surface"][next(iter(d["per_surface"]))].get("contrast"))
print("dataset:", d["dataset"], "rows:", d["n_rows_total"])
print("caps:", json.dumps(d["caps"], ensure_ascii=False))
print("verdict:", d["verdict"])
print()
hdr = f'{"surface":22s} {"rows":>5s} {"fibers":>7s} {"nontriv":>8s} {"valrel":>7s} {"kernel":>7s} {"opp":>4s} {"eps_lc":>9s}'
print(hdr)
print("-" * len(hdr))
for k, v in d["per_surface"].items():
    print(f'{k:22s} {v["n_rows"]:5d} {v["n_fibers"]:7d} '
          f'{v["n_nontrivial_fibers"]:8d} {v["n_value_relevant"]:7d} '
          f'{v["n_kernel_changed"]:7d} {v["n_opposite_sign_fibers"]:4d} '
          f'{v["epsilon_lc"]:9.4f}', end="")
    s = v.get("delta_sign")
    if s:
        print(f'  | keep+{s["n_keep_better"]:3d} arch+{s["n_archive_better"]:3d} '
              f'tau{s["n_within_tau"]:3d} range[{s["min"]:+.2f},{s["max"]:+.2f}]')
    else:
        print()
print()
for k, v in d["per_surface"].items():
    for w in v.get("top_witnesses", [])[:2]:
        print(f'  WITNESS {k}: score={w["score"]} eps_lc={w["epsilon_lc_witness"]} '
              f'regret>={w["regret_lower_bound"]} '
              f'keep={w["keep_row"]["msg_id"]}({w["keep_row"]["delta"]:+.3f}) '
              f'arch={w["archive_row"]["msg_id"]}({w["archive_row"]["delta"]:+.3f})')
