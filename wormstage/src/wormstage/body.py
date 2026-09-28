"""A planar servo snake under resistive-force-theory drag.

The robot is a chain of N rigid links joined by N-1 position-controlled
servos, crawling on a surface whose drag is anisotropic: pushing a link
sideways costs `K` times more than sliding it along its axis. This is the
same force law used for C. elegans (Gray & Hancock 1955; Boyle, Berri &
Cohen 2012), which is why one controller can be compared across worm and
robot: K ~ 1.5 is the worm in water, K ~ 40 is the worm on agar, and a
wheeled or finned robot sits in between.

Dynamics are overdamped (no inertia), as for the worm and for a slow
servo snake on a high-friction floor: at every instant the net external force
and torque are zero, which fixes the body's rigid velocity given the joint
velocities. That is a 3x3 linear solve per step.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Snake:
    n_links: int = 12
    link: float = 0.08          # m per link
    K: float = 10.0             # normal / tangential drag ratio
    servo_rate: float = 4.0     # rad/s max joint speed (hobby servo, loaded)
    servo_tau: float = 0.05     # s first-order servo lag
    joint_max: float = 1.0      # rad

    @property
    def length(self) -> float:
        return self.n_links * self.link

    def frames(self, pose: np.ndarray, phi: np.ndarray):
        """Link centres [N,2] and headings [N] from head pose (x, y, th) and joints."""
        th = pose[2] + np.concatenate([[0.0], np.cumsum(phi)])
        d = np.stack([np.cos(th), np.sin(th)], 1)
        # head link centre at pose; each next centre half a link back from the joint
        steps = -0.5 * self.link * (d[:-1] + d[1:])
        c = pose[:2] + np.concatenate([np.zeros((1, 2)), np.cumsum(steps, 0)])
        return c, th

    def body_velocity(self, pose, phi, dphi, eps=1e-6):
        """Solve for (vx, vy, w) of the head frame given joint rates."""
        c0, th0 = self.frames(pose, phi)
        # velocity of each link centre is linear in (v_pose, dphi): finite differences
        def vel(dpose, dph):
            c1, _ = self.frames(pose + eps * dpose, phi + eps * dph)
            return (c1 - c0) / eps

        cols = [vel(e, np.zeros_like(phi)) for e in np.eye(3)]
        shape_v = vel(np.zeros(3), dphi)
        t = np.stack([np.cos(th0), np.sin(th0)], 1)
        n = np.stack([-t[:, 1], t[:, 0]], 1)

        def drag(v):
            vt = np.sum(v * t, 1, keepdims=True)
            vn = np.sum(v * n, 1, keepdims=True)
            return -self.link * (vt * t + self.K * vn * n)

        def wrench(v):
            F = drag(v)
            r = c0 - c0.mean(0)
            return np.array([F[:, 0].sum(), F[:, 1].sum(),
                             np.sum(r[:, 0] * F[:, 1] - r[:, 1] * F[:, 0])])

        A = np.stack([wrench(cv) for cv in cols], 1)
        b = -wrench(shape_v)
        return np.linalg.solve(A, b)

    def step(self, pose, phi, target, dt):
        """Servos move toward targets; the body moves so drag balances."""
        target = np.clip(target, -self.joint_max, self.joint_max)
        rate = np.clip((target - phi) / self.servo_tau, -self.servo_rate, self.servo_rate)
        dpose = self.body_velocity(pose, phi, rate)
        return pose + dt * dpose, phi + dt * rate


def serpenoid(n_joints: int, t: float, amp=0.6, freq=0.5, waves=1.0) -> np.ndarray:
    """Hirose's serpenoid gait: a travelling sine of joint angles, head to tail."""
    i = np.arange(n_joints)
    return amp * np.sin(2 * np.pi * (freq * t - waves * i / n_joints))
