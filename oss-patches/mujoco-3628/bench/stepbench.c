// Step-time and line-search statistics on standard models, for google-deepmind/mujoco#3628.
//
// usage: stepbench model.xml nstep nrepeat [cone(0 pyramidal,1 elliptic,-1 keep)] [impratio]
//                  [ls_iterations]
// Runs nstep steps from the first keyframe (or qpos0) with deterministic pseudo-random controls,
// nrepeat times; prints the best wall time per step, and deterministic solver statistics.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <mujoco/mujoco.h>

static double now(void) {
  struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + 1e-9*t.tv_nsec;
}

int main(int argc, char** argv) {
  if (argc < 4) { fprintf(stderr, "usage\n"); return 1; }
  char err[1000];
  mjModel* m = mj_loadXML(argv[1], NULL, err, sizeof(err));
  if (!m) { fprintf(stderr, "%s\n", err); return 1; }
  int nstep = atoi(argv[2]), nrep = atoi(argv[3]);
  if (argc > 4 && atoi(argv[4]) >= 0) m->opt.cone = atoi(argv[4]);
  if (argc > 5) m->opt.impratio = atof(argv[5]);
  if (argc > 6) m->opt.ls_iterations = atoi(argv[6]);
  mjData* d = mj_makeData(m);

  double best = 1e30;
  long niter = 0, neval = 0, nexhaust = 0, nls = 0; int maxeval = 0; double chk = 0;
  for (int r=0; r < nrep; r++) {
    mj_resetData(m, d);
    if (m->nkey) mj_resetDataKeyframe(m, d, 0);
    uint64_t rng = 12345;
    niter = neval = nexhaust = nls = 0; maxeval = 0;
    double t0 = now();
    for (int s=0; s < nstep; s++) {
      for (int i=0; i < m->nu; i++) {
        rng = rng*6364136223846793005ull + 1442695040888963407ull;
        double u = ((rng >> 11) * (1.0/9007199254740992.0))*2 - 1;
        d->ctrl[i] = m->actuator_ctrllimited[i] ?
          m->actuator_ctrlrange[2*i] + 0.5*(u+1)*(m->actuator_ctrlrange[2*i+1]-m->actuator_ctrlrange[2*i]) : u;
      }
      mj_step(m, d);
      int nisland = d->nisland > 0 ? d->nisland : 1;
      for (int k=0; k < nisland && k < mjNISLAND; k++) {
        int n = d->solver_niter[k];
        niter += n;
        for (int i=0; i < n && i < mjNSOLVER; i++) {
          const mjSolverStat* st = d->solver + k*mjNSOLVER + i;
          nls++; neval += st->neval;
          if (st->neval > maxeval) maxeval = st->neval;
          if (st->neval >= m->opt.ls_iterations) nexhaust++;
        }
      }
    }
    double t = (now() - t0)/nstep;
    if (t < best) best = t;
    chk = 0; for (int i=0; i < m->nq; i++) chk += fabs(d->qpos[i]);
  }
  printf("%-40s cone=%d impratio=%g ls=%d nv=%d  step %.2f us  solver iters/step %.2f  "
         "LS evals mean %.2f max %d  exhausted %ld/%ld  sum|qpos| %.10g\n",
         argv[1], m->opt.cone, m->opt.impratio, m->opt.ls_iterations, (int)m->nv, 1e6*best,
         (double)niter/nstep, nls ? (double)neval/nls : 0.0, maxeval, nexhaust, nls, chk);
  mj_deleteData(d); mj_deleteModel(m);
  return 0;
}
