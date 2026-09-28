// Reproduction of google-deepmind/mujoco#3628 (the issue's Python script, ported to C).
// Build: cc repro.c -I$MJ/include -L$MJ_BUILD/lib -lmujoco -lm -o repro
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <mujoco/mujoco.h>

static const char* XML =
  "<mujoco>"
  "  <option timestep='0.0025' cone='elliptic' impratio='10' integrator='implicitfast'"
  "          iterations='100' tolerance='1e-8'/>"
  "  <worldbody>"
  "    <geom type='plane' size='5 5 .1'/>"
  "    <body pos='0 0 .3'><freejoint/><geom type='box' size='.2 .1 .05' mass='5'/></body>"
  "  </worldbody>"
  "</mujoco>";

static const double QPOS[7] = {-0.38228398123211904, -1.5617372196006747, 0.14420735808017446,
                               -0.3039178177313174, 0.6782960782869877, -0.6545711847046525,
                               -0.1381483058176044};
static const double QVEL[6] = {-2.5320433011146646, 0.4435273997725518, -3.833483970428372,
                               20.58784610148961, -4.891237201965733, -1.521169201653485};
static const double QACC_WS[6] = {196.2178511861834, 185.09984762860262, 456.16231234940415,
                                  -2622.9781161564592, 1990.857671015227, -729.4643685817738};

static mjModel* m;

static void solve(mjData* d, int ls, const double* ws) {
  m->opt.ls_iterations = ls;
  mj_resetData(m, d);
  for (int i=0; i < 7; i++) d->qpos[i] = QPOS[i];
  for (int i=0; i < 6; i++) d->qvel[i] = QVEL[i];
  for (int i=0; i < 6; i++) d->qacc_warmstart[i] = ws[i];
  mj_forward(m, d);
}

static void report(const char* label, mjData* d, const mjData* ref) {
  int n = d->solver_niter[0];
  double maxdif = 0;
  for (int i=0; i < 6; i++) maxdif = fmax(maxdif, fabs(d->qacc[i] - ref->qacc[i]));
  printf("%-26s niter %d, final gradient %.3g, neval [", label, n,
         n ? d->solver[(n < mjNSOLVER ? n : mjNSOLVER) - 1].gradient : NAN);
  for (int i=0; i < n && i < mjNSOLVER; i++) printf("%s%d", i ? ", " : "", d->solver[i].neval);
  printf("], max|qacc - qacc(ls 200)| %.3g\n", maxdif);
}

int main(void) {
  char err[1000];
  mjSpec* spec = mj_parseXMLString(XML, NULL, err, sizeof(err));
  if (!spec) { printf("%s\n", err); return 1; }
  m = mj_compile(spec, NULL);
  if (!m) { printf("compile failed\n"); return 1; }
  printf("MuJoCo %s, sizeof(mjtNum)=%zu, ncon after forward below\n", mj_versionString(), sizeof(mjtNum));
  mjData* ref = mj_makeData(m);
  mjData* d = mj_makeData(m);
  solve(ref, 200, QACC_WS);
  printf("ncon %d nefc %d\n", ref->ncon, ref->nefc);
  int lss[] = {20, 21, 22, 23, 50};
  for (int k=0; k < 5; k++) {
    char lbl[64]; snprintf(lbl, sizeof(lbl), "ls_iterations %d:", lss[k]);
    solve(d, lss[k], QACC_WS);
    report(lbl, d, ref);
  }
  solve(d, 20, QACC_WS);
  double q20[6]; memcpy(q20, d->qacc, sizeof(q20));
  solve(d, 20, q20);
  report("restart from ls 20 result:", d, ref);
  mj_deleteData(d); mj_deleteData(ref); mj_deleteModel(m); mj_deleteSpec(spec);
  return 0;
}
