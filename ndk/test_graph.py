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
"""Test for ndk.graph."""
import unittest
from typing import List, Optional, cast

import ndk.graph


def cycle_test(paths: List[str]) -> Optional[List[str]]:
    """Forms a graph from the given paths and returns the found cycle, if any.

    Args:
        paths: A list of paths. Each path is a list of node names. For each
            successive two nodes in a path (X, Y), an edge exists from X to Y.

    Returns:
        A list describing the cycle if one is found, else None.
    """
    node_names = sorted({n for p in paths for n in p})
    nodes = {n: ndk.graph.Node(n, []) for n in node_names}
    for p in paths:
        for i in range(len(p) - 1):
            nodes[p[i]].outs.append(nodes[p[i + 1]])
    graph = ndk.graph.Graph([nodes[n] for n in node_names])
    cycle = graph.find_cycle()
    if cycle is None:
        return None
    return [n.name for n in cycle]


class GraphTest(unittest.TestCase):
    def cycle_test(self, paths: List[str], expected: str) -> None:
        """Checks that a given cycle is found in a graph.

        Args:
            paths: A list of paths. Each path is a list of node names. For each
                successive two nodes in a path (X, Y), an edge exists from X to
                Y. For example, ['ACD', 'BC'] describes the following graph:

                    A -> C -> D
                    B -> C

            expected: An iterable describing the cycle path. For example, 'ABA'
                describes the cycle A -> B -> A.
        """
        cycle = cycle_test(paths)
        self.assertIsNotNone(cycle)
        self.assertListEqual(cast(List[str], cycle), list(expected))

    def test_self_cyclic(self) -> None:
        """Test that a cycle is found in a self-cyclic module."""
        self.cycle_test(["AA"], "AA")

    def test_no_source_raises(self) -> None:
        """Test that a cycle is found in a graph with no source."""
        self.cycle_test(["ABCA"], "ABCA")

    def test_find_cycle(self) -> None:
        """Test that cycles can be found."""
        self.cycle_test(["ABCDB"], "BCDB")
        self.cycle_test(["ABCB", "BD"], "BCB")
        self.cycle_test(["CBA", "CDC"], "CDC")

    def test_no_cycle(self) -> None:
        """Test that None is returned when there is no cycle."""
        self.assertIsNone(cycle_test(["ABCD", "CEF"]))
