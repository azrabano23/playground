"""loopgraph: a harness for research that runs itself.

    graph   -- content-addressed DAG of pure pipeline stages
"""

from .graph import Graph, GraphError, Node, RunResult, node, stable_hash

__all__ = ["Graph", "GraphError", "Node", "RunResult", "node", "stable_hash"]
__version__ = "0.1.0"
