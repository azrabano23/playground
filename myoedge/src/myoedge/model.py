"""Classifiers: LDA (the clinical baseline) and a small softmax MLP.

Both produce a list of (W, b) layers on standardised features, which
loopgraph.int8 quantises and emits; the standardisation folds into the
integer prep stage, as in pocketpolicy.
"""

from __future__ import annotations

import numpy as np

N_CLASSES = 5


def standardise(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return X.mean(0), X.std(0) + 1e-6


def fit_lda(Z: np.ndarray, y: np.ndarray, shrink: float = 1e-3):
    mu = np.array([Z[y == c].mean(0) for c in range(N_CLASSES)])
    S = sum(np.cov(Z[y == c].T) * (np.sum(y == c) - 1) for c in range(N_CLASSES))
    S = S / (len(y) - N_CLASSES)
    S += shrink * np.eye(Z.shape[1]) * np.trace(S) / Z.shape[1]
    W = mu @ np.linalg.inv(S)
    return [(W, -0.5 * np.sum(W * mu, 1))]


def fit_mlp(Z: np.ndarray, y: np.ndarray, hidden: int, epochs: int = 60, lr: float = 3e-3,
            batch: int = 128, seed: int = 0, l2: float = 1e-4):
    rng = np.random.default_rng(seed)
    dims = [Z.shape[1], hidden, N_CLASSES]
    L = [(rng.normal(0, np.sqrt(2 / i), (o, i)), np.zeros(o)) for i, o in zip(dims[:-1], dims[1:])]
    m = [(np.zeros_like(W), np.zeros_like(b)) for W, b in L]
    v = [(np.zeros_like(W), np.zeros_like(b)) for W, b in L]
    Y = np.eye(N_CLASSES)[y]
    t = 0
    for _ in range(epochs):
        idx = rng.permutation(len(Z))
        for s in range(0, len(Z), batch):
            j = idx[s:s + batch]
            h = np.maximum(Z[j] @ L[0][0].T + L[0][1], 0)
            o = h @ L[1][0].T + L[1][1]
            p = np.exp(o - o.max(1, keepdims=True))
            p /= p.sum(1, keepdims=True)
            g = (p - Y[j]) / len(j)
            grads = [None, (g.T @ h + l2 * L[1][0], g.sum(0))]
            gh = (g @ L[1][0]) * (h > 0)
            grads[0] = (gh.T @ Z[j] + l2 * L[0][0], gh.sum(0))
            t += 1
            for i, ((W, b), (gW, gb)) in enumerate(zip(L, grads)):
                for P, G, M, V in ((W, gW, m[i][0], v[i][0]), (b, gb, m[i][1], v[i][1])):
                    M[:] = 0.9 * M + 0.1 * G
                    V[:] = 0.999 * V + 0.001 * G * G
                    P -= lr * (M / (1 - 0.9**t)) / (np.sqrt(V / (1 - 0.999**t)) + 1e-8)
    return L


def predict(layers, Z: np.ndarray) -> np.ndarray:
    a = Z
    for i, (W, b) in enumerate(layers):
        a = a @ W.T + b
        if i < len(layers) - 1:
            a = np.maximum(a, 0)
    return a.argmax(1)
