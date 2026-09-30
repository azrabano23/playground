// Line-search statistics over 200 steps: usage lscount model.xml tolerance [cone] [solver 1=CG 2=Newton]
#include <stdio.h>
#include <stdlib.h>
#include <mujoco/mujoco.h>
int main(int argc, char** argv) {
  char err[1000];
  mjModel* m = mj_loadXML(argv[1], NULL, err, 1000);
  m->opt.tolerance = atof(argv[2]);
  if (argc > 3) m->opt.cone = atoi(argv[3]);
  if (argc > 4) m->opt.solver = atoi(argv[4]);
  mjData* d = mj_makeData(m);
  if (m->nkey) mj_resetDataKeyframe(m, d, 0);
  long nls = 0, nex = 0, nev = 0, nit = 0;
  for (int s = 0; s < 200; s++) {
    mj_step(m, d);
    for (int k = 0; k < (d->nisland > 0 ? d->nisland : 1); k++) {
      int n = d->solver_niter[k]; nit += n;
      for (int i = 0; i < n && i < mjNSOLVER; i++) { nls++; nev += d->solver[k*mjNSOLVER+i].neval; nex += d->solver[k*mjNSOLVER+i].neval >= m->opt.ls_iterations; }
    }
  }
  printf("tol %g: iters %ld  LS %ld  mean evals %.2f  exhausted %ld\n", m->opt.tolerance, nit, nls, nls ? (double)nev/nls : 0., nex);
  return 0;
}
