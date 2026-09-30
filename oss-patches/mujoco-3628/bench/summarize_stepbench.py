# Summarize run_stepbench.sh output: min and median step time per variant, and the median of
# per-round paired ratios fix/base (rounds alternate base and fix, so pairs share machine load).
import collections, re, statistics, sys
rows = collections.defaultdict(list); info = {}
for l in open(sys.argv[1]):
  m = re.match(r'(\w+) (\w+) (\S+)\s+cone=(\d) impratio=(\S+) ls=(\d+) nv=(\d+)\s+step ([\d.]+) us'
               r'\s+solver iters/step ([\d.]+)\s+LS evals mean ([\d.]+) max (\d+)\s+exhausted (\d+)/(\d+)', l)
  if not m:
    continue
  prec, v, model, cone, imp = m.group(1, 2, 3, 4, 5)
  key = (prec, model, 'elliptic' if cone == '1' else 'pyramidal', imp)
  rows[(key, v)].append(float(m.group(8)))
  info[(key, v)] = m.group(9, 10, 11, 12, 13)
n = len(next(iter(rows.values())))
print(f'Step time over {n} interleaved rounds (base, fix alternating). Shared, loaded 4-core VM:'
      ' timings are noisy; LS statistics are deterministic.')
print(f"{'prec':6} {'model':38} {'cone':9} {'imp':>3} | {'base min':>8} {'fix min':>8} | {'paired fix/base median':>22} |"
      f" {'iters/step b/f':>15} | {'LS evals mean b/f':>17} | {'max b/f':>7} | exhausted b/f")
for (key, v), t in sorted(rows.items()):
  if v != 'base':
    continue
  f = rows[(key, 'fix')]
  ratio = statistics.median(fi / bi for fi, bi in zip(f, t))
  ib, i_f = info[(key, 'base')], info[(key, 'fix')]
  print(f'{key[0]:6} {key[1]:38} {key[2]:9} {key[3]:>3} | {min(t):8.1f} {min(f):8.1f} | {ratio:22.3f} |'
        f' {ib[0]:>7}/{i_f[0]:<7} | {ib[1]:>8}/{i_f[1]:<8} | {ib[2]:>3}/{i_f[2]:<3} | {ib[3]}/{ib[4]} vs {i_f[3]}/{i_f[4]}')
