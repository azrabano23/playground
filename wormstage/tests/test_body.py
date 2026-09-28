import numpy as np

from wormstage.body import Snake, serpenoid


def run(K, T=12.0, dt=0.02, **kw):
    kw.setdefault("compliant", False)
    s = Snake(K=K, **kw)
    pose, phi = np.zeros(3), np.zeros(s.n_links - 1)
    for k in range(int(T / dt)):
        pose, phi = s.step(pose, phi, serpenoid(s.n_links - 1, k * dt), dt)
    return s, pose, phi


def test_frames_are_a_connected_chain():
    s = Snake(n_links=5)
    c, th = s.frames(np.array([1.0, 2.0, 0.3]), np.array([0.2, -0.1, 0.4, 0.0]))
    gaps = np.linalg.norm(np.diff(c, axis=0), axis=1)
    assert np.all(gaps <= s.link + 1e-12) and np.all(gaps > 0.9 * s.link)


def test_isotropic_drag_gives_almost_no_net_motion():
    _, p_iso, _ = run(1.0)
    _, p_agar, _ = run(40.0)
    assert np.linalg.norm(p_iso[:2]) < 0.1 * np.linalg.norm(p_agar[:2])


def test_speed_increases_with_anisotropy():
    d = [np.linalg.norm(run(K)[1][:2]) for K in (1.5, 10.0, 40.0)]
    assert d[0] < d[1] < d[2]


def test_head_to_tail_wave_moves_head_first():
    _, pose, _ = run(10.0)
    assert pose[0] > 0.5  # the head started at the origin facing +x


def test_servo_limits():
    s = Snake(n_links=4, servo_rate=2.0, joint_max=0.5, compliant=False)
    pose, phi = np.zeros(3), np.zeros(3)
    _, phi2 = s.step(pose, phi, np.full(3, 5.0), 0.01)
    assert np.allclose(phi2, 0.02)


def test_compliant_mode_is_stable_in_low_drag():
    """Regression: explicit Euler chattered at the Nyquist rate for K=1.5."""
    s = Snake(K=1.5, compliant=True)
    pose, phi = np.zeros(3), np.zeros(s.n_links - 1)
    dt = 0.02
    P = []
    for k in range(600):
        pose, phi = s.step(pose, phi, serpenoid(s.n_links - 1, k * dt, amp=0.5, freq=0.8), dt)
        P.append(phi[3])
    x = np.array(P[200:])
    flips = np.sum(np.diff(np.sign(np.diff(x))) != 0)
    assert flips < 40  # 0.8 Hz over 8 s has ~13 peaks and troughs, not hundreds


def test_soft_joints_yield_to_the_medium():
    amps = []
    for K in (1.5, 40.0):
        s = Snake(K=K, compliant=True, k_joint=0.02)
        pose, phi = np.zeros(3), np.zeros(s.n_links - 1)
        P = []
        for k in range(600):
            pose, phi = s.step(pose, phi, serpenoid(s.n_links - 1, k * 0.02, 0.5, 0.8), 0.02)
            P.append(phi.copy())
        amps.append(np.std(np.array(P[200:]), 0).mean())
    assert amps[1] < 0.8 * amps[0]
