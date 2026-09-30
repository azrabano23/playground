# Experience: canonical bullet bank

Each entry gives the canonical header, stack, and bullets ordered strongest-first. Pick 1–3
bullets per entry when tailoring. Bracketed tags cite `raw/SOURCES.md`.

## Google, Software Engineering Intern, YouTube Ads Infrastructure
Mountain View, CA · May 2026 – Aug 2026 · [R1, R3, R5]
**Stack:** C++, Spanner, Protocol Buffers, RaphtQ (event queue), CNS, distributed checkpointing
- Cut distributed server recovery time **99.7% (60 min → 10 s)** across **100+ leaf servers and 10+
  services** by replacing a synchronous RPC recovery path with a push-based, event-driven queue
  sustaining up to **2B edges/s**. [R1, R3]
- Removed **~50 min of degraded capacity per incident** for forecasting allocation servers. [R3, R5]
- Shipped production C++ checkpointing and recovery components on Spanner, with Protocol Buffers
  for schema-stable serialization across services. [R3]
- Replaced subjective launch review with measurable scenario-coverage criteria and automated
  regression checks that gate rollout; reported results to 3 owning teams. [R3, R4]
- Owned the project end to end within the 14-week internship. [R3]

## Columbia University Center for AI (with IEEE, INNS): Applied SWE & Quantum ML Researcher
New York, NY · Mar 2025 – May 2026 · [R1, R3, R8]
**Stack:** Python, PyTorch, Qiskit (IBM quantum hardware), variational quantum circuits, Equilibrium Propagation
- **First author, arXiv:2601.18710**: trained **4 model families** (CNN, dense, Equilibrium
  Propagation, 4-qubit variational circuit) from scratch across **5 dataset scales** on **18,365
  expert-annotated** AML blood-cell images, measuring accuracy, convergence and runtime. [R3, R8]
- Reported the **12–15% gap** to classical baselines and the simulation limits instead of a
  best-case number; ran circuits on IBM quantum hardware. [R3, GitHub quantum-blood-cell-classification]

## NASA: Technical Lead, Swarm Robotics Intelligence
Newark, NJ · Nov 2025 – May 2026 · [R1, R2, R3]
**Stack:** C++, Python, decentralized multi-agent coordination, fault tolerance, real-time systems
- Led architecture of a decentralized, fault-tolerant multi-agent software stack for a NASA-funded
  heterogeneous robot swarm doing self-assembly for lunar construction: inter-agent protocols,
  no central controller, degraded-unit recovery. [R2, R3]
- Open-sourced the decentralized self-assembly algorithm (`robrick-selfassembly-algorithm`);
  delivered technical reviews to NASA stakeholders. [R2, R7]

## NASA × XFoundry Horizons 2040: Lead Systems & ML Engineer, 1st Nationally
Arlington, VA · May 2025 – Oct 2025 · [R1, R2, R3]
**Stack:** Python, C++, Java, time-series modeling, cloud-native services, Linux
- Won **1st of 290+ teams from 21 universities** leading a **15+ person** team on InnerSolace, an AI
  circadian-rhythm platform simulating **100+ mission-day scenarios** across orbital and polar
  environments over thousands of daily biometric and light-cycle data points. [R1, R3]

## Goldman Sachs: Software Engineering Emerging Leader & First-Year Team
Dallas, TX · Sep 2024 – May 2026 · [R1, R3]
**Stack:** Java, Spring Boot, Angular, Monte Carlo simulation, CAPM
- Built a Java backtesting engine for a fund-forecasting platform with CAPM alpha modeling, Monte
  Carlo path simulation and Sharpe-based scoring across **3 risk profiles** and multi-decade horizons. [R3]
- Prototyped low-latency, high-throughput data pipelines, benchmarked throughput against
  reliability, and presented the architecture to engineering leadership at Goldman HQ. [R1, R3]

## Rutgers WINLAB (with MIT): Software Engineering & XR Intern
North Brunswick, NJ · May 2025 – Sep 2025 · [R1, R3]
**Stack:** C++, Python, Linux, Docker, CI/CD, distributed tracing, REST
- Built real-time telemetry and observability infrastructure across **2 physical edge platforms**:
  async pipelines from heterogeneous sensor and simulation sources, structured logging and
  distributed tracing, replacing manual debugging with reproducible fault triage. [R3]

## NSF I-Corps × Princeton University: Technical Lead
Princeton, NJ · Mar 2025 – Nov 2025 · [R1, R3]
**Stack:** cross-platform app, backend services
- Ran **40+ structured stakeholder interviews**, turned findings into a prioritized backlog, and led
  the cross-platform build for reliability in financial systems. [R1, R3]

## Rutgers Sensing & Reasoning Lab
**Unverified; do not put on a resume yet.** See `profile.md` § Open questions 3.

## Y Combinator (hackathon, Startup School)
Listed under `awards.md` and `projects.md` (Nomos). Older masters presented it as an experience
entry. On space-constrained resumes it is a project with "#1, YC RL Hackathon" in the title.
Startup School attendee (selected from 30K+ applicants). [R1]
