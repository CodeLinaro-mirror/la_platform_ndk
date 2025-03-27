#
# Copyright (C) 2018 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Graph classes and functions."""
import functools
from typing import Iterable, List, Optional, Set


@functools.total_ordering
class Node:
    """A node in a directed graph."""

    def __init__(self, name: str, outs: Iterable["Node"]) -> None:
        """Initializes a Node.

        Args:
            name: The name of this node.
            outs: Nodes with an edge leading out from this node.
        """
        self.name = name
        self.outs = sorted(list(outs))

    def __repr__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Node)
        return self.name == other.name

    def __lt__(self, other: object) -> bool:
        assert isinstance(other, Node)
        return self.name < other.name

    def __hash__(self) -> int:
        return hash(str(self))


class Graph:
    """A directed graph."""

    def __init__(self, nodes: Iterable[Node]) -> None:
        """Initializes a Graph.

        Args:
            nodes: A list of nodes in this graph.
        """
        self.nodes = sorted(list(nodes))

    def find_cycle(self) -> Optional[List[Node]]:
        """Finds a cycle in the graph if there is one.

        Returns:
            A list of nodes that make up a cycle or None if no cycle exists.
            The list will begin and end with the same node, i.e. [A, B, A].
        """
        visited: Set[Node] = set()
        for node in self.nodes:
            cycle = self.find_cycle_from_node(node, visited)
            if cycle is not None:
                return cycle
        return None

    def find_cycle_from_node(
        self, node: Node, visited: Set[Node], path: Optional[List[Node]] = None
    ) -> Optional[List[Node]]:
        """Finds a cycle from a given node if there is one.

        Performs a recursive depth-first search to see if there are any cycles
        in a connected component. The caller of this method should ensure that
        the first node searched is a source node if there is one, as this
        method will not backtrack to find cycles prior to the given node.

        If there is no source node in the connected component, there is
        certainly a cycle in the component, but this method can still be used
        to trace that cycle.

        Args:
            node: Current node to check for cycles.
            visied: A set of all nodes that have been previously checked. Used
                to short circuit searching.
            path: A list containing the path to the current node from the first
                node.

        Returns:
            A list of nodes that make up a cycle or None if no cycle exists.
            The list will begin and end with the same node, i.e. [A, B, A].
        """
        if path is None:
            path = []

        path.append(node)
        if node in path[:-1]:
            return path[path.index(node) :]

        if node in visited:
            path.pop()
            return None

        visited.add(node)
        for in_node in node.outs:
            cycle = self.find_cycle_from_node(in_node, visited, path)
            if cycle is not None:
                return cycle
        path.pop()
        return None
