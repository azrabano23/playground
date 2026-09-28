// 40k-solve protocol for google-deepmind/mujoco#3628.
//
// A free box (the issue's model) is dropped from random poses with random velocity kicks.
// The trajectory is driven with a converged reference solver (ls_iterations=200). At every
// step the state (qpos, qvel, qacc_warmstart) is copied into a second mjData and solved
// with the configuration under test; the resulting qacc is compared against the reference.
//
// usage: bench40k [cone: elliptic|pyramidal] [impratio] [ls_iterations] [nsolve] [seed]
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <mujoco/mujoco.h>

static uint64_t rng = 88172645463325252ull;
static double urand(void) {  // xorshift64, uniform in [0, 1)
  rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
  return (rng >> 11) * (1.0 / 9007199254740992.0);
}
static double uni(double a, double b) { return a + (b - a)*urand(); }
static double now(void) {
  struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + 1e-9*t.tv_nsec;
}

static int nwarn_seen = 0;
static void warn_cb(const char* msg) { if (nwarn_seen++ < 3) fprintf(stderr, "[warning] %s\n", msg); }

static void kick(const mjModel* m, mjData* d, int reset) {
  if (reset) {
    mj_resetData(m, d);
    d->qpos[0] = uni(-1, 1); d->qpos[1] = uni(-1, 1); d->qpos[2] = uni(0.06, 0.4);
    double q[4] = {uni(-1, 1), uni(-1, 1), uni(-1, 1), uni(-1, 1)};
    mju_normalize4(q);
    for (int i=0; i < 4; i++) d->qpos[3+i] = q[i];
  }
  for (int i=0; i < 3; i++) d->qvel[i] = uni(-4, 4);
  for (int i=3; i < 6; i++) d->qvel[i] = uni(-25, 25);
}

int main(int argc, char** argv) {
  const char* cone = argc > 1 ? argv[1] : "elliptic";
  const char* impratio = argc > 2 ? argv[2] : "10";
  int ls = argc > 3 ? atoi(argv[3]) : 20;
  int nsolve = argc > 4 ? atoi(argv[4]) : 40000;
  if (argc > 5) rng = strtoull(argv[5], NULL, 10) * 2654435761ull + 1;

  char xml[1024], err[1000];
  snprintf(xml, sizeof(xml),
    "<mujoco><option timestep='0.0025' cone='%s' impratio='%s' integrator='implicitfast'"
    " iterations='100' tolerance='1e-8'/><worldbody><geom type='plane' size='5 5 .1'/>"
    "<body pos='0 0 .3'><freejoint/><geom type='box' size='.2 .1 .05' mass='5'/></body>"
    "</worldbody></mujoco>", cone, impratio);
  mjSpec* spec = mj_parseXMLString(xml, NULL, err, sizeof(err));
  if (!spec) { fprintf(stderr, "%s\n", err); return 1; }
  mjModel* m = mj_compile(spec, NULL);
  mju_user_warning = warn_cb;

  mjData* d = mj_makeData(m);      // reference trajectory
  mjData* t = mj_makeData(m);      // test solve
  int nstate = mj_stateSize(m, mjSTATE_FULLPHYSICS | mjSTATE_WARMSTART);
  mjtNum* state = malloc(sizeof(mjtNum)*nstate);

  long ncontact = 0, ndev1 = 0, nunconv = 0, nfixed = 0, niter_sum = 0, neval_sum = 0;
  int neval_max = 0; double maxdev = 0, tsolve = 0;
  long nls_exhaust = 0;
  kick(m, d, 1);
  for (int s=0; s < nsolve; s++) {
    if (s % 200 == 0) kick(m, d, 1);          // new drop every 200 steps
    else if (s % 50 == 0) kick(m, d, 0);      // velocity kick every 50 steps

    // reference step from the current state
    m->opt.ls_iterations = 200;
    mj_getState(m, d, state, mjSTATE_FULLPHYSICS | mjSTATE_WARMSTART);
    mj_forward(m, d);

    // test solve from the same state
    m->opt.ls_iterations = ls;
    mj_setState(m, t, state, mjSTATE_FULLPHYSICS | mjSTATE_WARMSTART);
    double t0 = now();
    mj_forward(m, t);
    tsolve += now() - t0;

    if (t->ncon) {
      ncontact++;
      double dev = 0;
      for (int i=0; i < m->nv; i++) dev = fmax(dev, fabs(t->qacc[i] - d->qacc[i]));
      maxdev = fmax(maxdev, dev);
      ndev1 += dev > 1;
      int n = t->solver_niter[0];
      niter_sum += n;
      for (int i=0; i < n && i < mjNSOLVER; i++) {
        neval_sum += t->solver[i].neval;
        if (t->solver[i].neval > neval_max) neval_max = t->solver[i].neval;
        nls_exhaust += t->solver[i].neval >= ls;
      }
      double grad = n ? t->solver[(n < mjNSOLVER ? n : mjNSOLVER) - 1].gradient : 0;
      if (grad > 1e-3) {
        nunconv++;
        // false fixed point: restart from the returned qacc
        mju_copy(t->qacc_warmstart, t->qacc, m->nv);
        mj_forward(m, t);
        if (t->solver_niter[0] == 0) nfixed++;
      }
    }

    // advance the reference trajectory
    m->opt.ls_iterations = 200;
    mj_step(m, d);
    if (d->qpos[2] < -1 || d->qpos[2] > 10) kick(m, d, 1);
  }
  printf("cone=%s impratio=%s ls_iterations=%d mjtNum=%zuB solves=%d with_contact=%ld\n",
         cone, impratio, ls, sizeof(mjtNum), nsolve, ncontact);
  printf("  |qacc-ref|>1: %ld  (max %.3g)\n", ndev1, maxdev);
  printf("  final gradient>1e-3: %ld   of which restart gives 0 iterations: %ld\n", nunconv, nfixed);
  printf("  line searches: %ld  mean evals %.2f  max evals %d  exhausted(neval>=ls) %ld\n",
         niter_sum, niter_sum ? (double)neval_sum/niter_sum : 0.0, neval_max, nls_exhaust);
  printf("  mean newton iters %.3f  mean mj_forward time %.2f us\n",
         ncontact ? (double)niter_sum/ncontact : 0.0, 1e6*tsolve/nsolve);
  printf("  warnings printed: %d\n", nwarn_seen);
  return 0;
}
