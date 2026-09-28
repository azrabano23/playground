"""loopgraph: a harness for research that runs itself.

    graph   -- content-addressed DAG of pure pipeline stages
    ledger  -- append-only run record, gates, and claims checked against it
    agents  -- planners (grid, random, Pareto, committee) and the campaign loop
    llm     -- a language-model planner behind the same interface
    int8    -- int8 MLP quantizer, exact integer reference, C99 emitter
    cgate   -- gates that compile and run C and compare it bit-for-bit
"""

from .agents import (Campaign, Committee, GridDecider, Objective, ParetoDecider, Proposal,
                     RandomDecider, pareto_front)
from .graph import Graph, GraphError, Node, RunResult, node, stable_hash
from .ledger import Claim, Entry, Gate, Ledger, at_least, at_most, equals, record, verify_claims

__all__ = [
    "Campaign", "Claim", "Committee", "Entry", "Gate", "Graph", "GraphError", "GridDecider",
    "Ledger", "Node", "Objective", "ParetoDecider", "Proposal", "RandomDecider", "RunResult",
    "at_least", "at_most", "equals", "node", "pareto_front", "record", "stable_hash",
    "verify_claims",
]
__version__ = "0.1.0"
