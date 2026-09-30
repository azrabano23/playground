// Master resume: frontier AI + quant + systems. Tailored copies go in career/applications/<slug>/.
// Every fact here is in career/wiki; do not add one that is not.
#import "/career/resume/template.typ": *

#let phone = sys.inputs.at("phone", default: none)
#let gh = "https://github.com/azrabano23"

#show: resume.with(
  name: "Azra Bano",
  contact: (
    ..if phone != none { (phone,) },
    u("mailto:azra.bano@rutgers.edu", "azra.bano@rutgers.edu"),
    u("https://www.linkedin.com/in/meetazrabano", "linkedin.com/in/meetazrabano"),
    u(gh, "github.com/azrabano23"),
    u("https://arxiv.org/abs/2601.18710", "arXiv:2601.18710"),
  ),
)

#section("Education")
#entry(
  [Rutgers University–New Brunswick, School of Engineering], [Expected Aug 2027],
  role: [B.S. Electrical & Computer Engineering and Mathematics; minors in Computer Science, Data Science],
  place: [New Brunswick, NJ],
)

#section("Experience")
#entry(
  [Google], [May 2026 – Aug 2026],
  role: [Software Engineering Intern, YouTube Ads Infrastructure], place: [Mountain View, CA],
  stack: [C++, Spanner, Protocol Buffers, RaphtQ event queue, CNS, distributed checkpointing],
  bullets: (
    [Cut distributed server recovery time *99.7% (60 min → 10 s)* across 100+ leaf servers and 10+ services by replacing a synchronous RPC recovery path with a push-based event queue sustaining up to *2B edges/s*.],
    [Shipped production C++ checkpoint/recovery components on Spanner, removing *\~50 min of degraded capacity per incident*; gated rollout on automated scenario-coverage regression checks.],
  ),
)
#entry(
  [Columbia University Center for AI (with IEEE, INNS)], [Mar 2025 – May 2026],
  role: [Applied SWE & Quantum ML Researcher, #u("https://arxiv.org/abs/2601.18710", "first author, arXiv:2601.18710")], place: [New York, NY],
  stack: [Python, PyTorch, Qiskit on IBM quantum hardware, variational circuits, Equilibrium Propagation],
  bullets: (
    [Trained *4 model families* (CNN, dense, Equilibrium Propagation, 4-qubit variational circuit) from scratch across *5 dataset scales* on *18,365* expert-labeled leukemia cell images; reported the *12–15%* gap to classical baselines instead of a best case.],
  ),
)
#entry(
  [NASA: Swarm Robotics Intelligence & XFoundry Horizons 2040], [May 2025 – May 2026],
  role: [Technical Lead; Lead Systems & ML Engineer], place: [Newark, NJ & Arlington, VA],
  stack: [C++, Python, decentralized multi-agent coordination, fault tolerance, time-series modeling],
  bullets: (
    [Led a *15+ person* team to *1st of 290+ teams from 21 universities* with InnerSolace, simulating *100+ mission-day* circadian scenarios across orbital and polar environments.],
    [Architected decentralized, fault-tolerant multi-agent software for a NASA-funded heterogeneous swarm doing lunar self-assembly (no central controller, degraded-unit recovery); #u(gh + "/robrick-selfassembly-algorithm", "open-sourced the algorithm").],
  ),
)
#entry(
  [Goldman Sachs], [Sep 2024 – May 2026],
  role: [Software Engineering Emerging Leader & First-Year Team], place: [Dallas, TX],
  stack: [Java, Spring Boot, Monte Carlo simulation, CAPM, low-latency data pipelines],
  bullets: (
    [Built a Java backtesting engine with CAPM alpha, Monte Carlo path simulation and Sharpe-based scoring across *3 risk profiles*; presented the low-latency pipeline design to engineering leadership at HQ.],
  ),
)
#entry(
  [Rutgers WINLAB (with MIT)], [May 2025 – Sep 2025],
  role: [Software Engineering & XR Intern], place: [North Brunswick, NJ],
  stack: [C++, Python, Linux, Docker, CI/CD, distributed tracing],
  bullets: (
    [Built real-time telemetry across *2 physical edge platforms* (async ingest, structured logging, distributed tracing), replacing manual debugging with reproducible fault triage.],
  ),
)
#entry(
  [NSF I-Corps × Princeton University], [Mar 2025 – Nov 2025],
  role: [Technical Lead], place: [Princeton, NJ],
  stack: [cross-platform app, backend services],
  bullets: (
    [Ran *40+* stakeholder interviews and led the cross-platform build, using the findings to improve reliability in financial systems.],
  ),
)

#section("Research & Projects")
#item([#u(gh + "/playground", "Integer-C models for microcontrollers")], [Three models compiled to malloc-free, float-free C99, bit-exact vs. NumPy, every number CI-checked against a run ledger: robot policy at *90.5%* success in *6.4 KB* (pocketpolicy); EMG decoder restoring post-shift accuracy *52% → 90%* in *456 B* (myoedge); connectome-driven snake robot (wormstage). _Python, int8, C99, agent-run experiment graph._])
#item([Nomos: \#1 ML Research, YC RL Hackathon], [Shared-parameter MAPPO in parallel JAX worlds coordinating *172* driverless agents on the SF road graph; constrained PPO plus a CBF-QP safety filter reach *98.7%* collision-free. _JAX, MARL._])
#item([#u(gh + "/interp", "interp")], [Mechanistic-interpretability CLI (logit lens, DLA, SAE features, steering) reproducing *2* published GPT-2 circuits at causal-patching recovery *≈1.0*. _PyTorch._])
#item([#u(gh + "/evalkit", "evalkit")], [LLM-eval statistics: bootstrap CIs at *90% → 91%* empirical coverage, exact pass\@k and McNemar tests, judge position-bias detection (recovery *1.00*), 13-gram contamination checks. _NumPy._])
#item([#u(gh + "/AeroBin", "AeroBin")], [Verizon Smart Campus National Winner: fill prediction and capacitated routing cut wasteful pickups *87% → 0.5%* across *3* pilots. _React, TypeScript._])

#section("Open Source")
#block(spacing: 0.34em)[*8 merged upstream PRs:* statsmodels ×3 (#u("https://github.com/statsmodels/statsmodels/pull/10230", "Holt-Winters seasonal bug"), #u("https://github.com/statsmodels/statsmodels/pull/10232", "out-of-bounds write")), #u("https://github.com/UKGovernmentBEIS/inspect_evals/pull/1765", "UK AISI inspect_evals #1765"), #u("https://github.com/TransformerLensOrg/TransformerLens/pull/1369", "TransformerLens #1369"), #u("https://github.com/NeuroTechX/moabb/pull/1140", "moabb #1140"), nnsight, braindecode. *Open:* #u("https://github.com/ai-dynamo/dynamo/pull/13326", "NVIDIA Dynamo #13326"), #u("https://github.com/flashinfer-ai/flashinfer/pull/4548", "FlashInfer #4548"), #u("https://github.com/skypilot-org/skypilot/pull/10484", "SkyPilot #10484"). Every fix starts from a reproducing case.]

#section("Awards & Leadership")
#block(spacing: 0.34em)[1st nationally, NASA × XFoundry Horizons 2040 (290+ teams) · \#1 ML Research, YC RL Hackathon · Verizon Smart Campus National Winner · Defense Track Winner, JacHacks (#u(gh + "/BlackStart", "BLACKSTART")) · 3rd, Daytona HackSprint · Rutgers Innovation Award (20 of 60,000+). Founder, #u("https://medicine.yale.edu/neurology/education/grey-matter-project/", "Grey Matter Society") (150+ chapters, with Yale School of Medicine); elected Engineering Representative for 40,000+ students.]

#section("Technical Skills")
#skills((
  ("Languages", "C++, Python, Java, C, Rust, TypeScript, SQL, R"),
  ("Systems", "distributed systems, event-driven queues, Spanner, Protocol Buffers, checkpoint/recovery, Kubernetes, Docker, Linux, CI/CD"),
  ("ML", "PyTorch, JAX, multi-agent RL, mechanistic interpretability, SAEs, LLM evaluation, int8 quantization, Qiskit"),
  ("Quant", "time-series (ARIMA/SARIMAX, Holt-Winters), Monte Carlo, bootstrap CIs, hypothesis testing, portfolio optimization"),
))
