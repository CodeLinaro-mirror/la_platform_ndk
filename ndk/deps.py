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
"""Performs dependency tracking for ndk.builds modules."""
from typing import Dict, Iterable, List, Set

import ndk.graph
from ndk.builds import Module


class CyclicDependencyError(RuntimeError):
    """An error indicating a cyclic dependency in the module graph."""

    def __init__(self, modules: Iterable[ndk.graph.Node]) -> None:
        """Initializes a CyclicDependencyError."""
        super().__init__(
            "Detected cyclic dependency: {}".format(
                " -> ".join([m.name for m in modules])
            )
        )


def prove_acyclic(modules: Iterable[Module]) -> None:
    """Proves that the graph is acyclic or raises an error.

    Args:
        modules: A list of all modules in the graph.

    Raises:
        CyclicDependencyError: A cycle was found in the module graph.
    """
    nodes = {m.name: ndk.graph.Node(m.name, []) for m in modules}
    for module in modules:
        for dep in module.deps:
            nodes[module.name].outs.append(nodes[dep])
    graph = ndk.graph.Graph(nodes.values())
    cycle = graph.find_cycle()
    if cycle is not None:
        raise CyclicDependencyError(cycle)


class DependencyManager:
    """Tracks module dependencies.

    The DependencyManager computes module ordering based on the dependency
    graph and exposes DependencyManager.get_buildable() as the list of modules
    that are no longer waiting on their dependencies. This is updated whenever
    the DependencyManager is informated of a module build being completed via
    DependencyManager.complete().
    """

    def __init__(self, all_modules: Iterable[Module]) -> None:
        """Initializes a DependencyManager."""
        if not all_modules:
            raise ValueError
        prove_acyclic(all_modules)

        self.buildable_modules = {m for m in all_modules if not m.deps}

        # The values of this map are the modules that the key is still waiting
        # for. When a build is complete, it is removed from all values in this
        # dict. An empty value indicates that the module is now buildable.
        self.blocked_modules = {m: set(m.deps) for m in all_modules if m.deps}

        # Reverse map from a module to all of its dependents used to speed up
        # lookups.
        self.deps_to_modules: Dict[str, List[Module]] = {
            m.name: [] for m in all_modules
        }
        for module in all_modules:
            for dep in module.deps:
                self.deps_to_modules[dep].append(module)

    def get_buildable(self) -> Set[Module]:
        """Returns a set of modules that are ready to be built.

        Retrieving the list of buildable modules removes them from the
        buildable_modules set. This is done because it is assumed that the
        caller will use the retrieved set to start those builds and the
        buildable set should not include active builds.
        """
        buildable = self.buildable_modules
        self.buildable_modules = set()
        return buildable

    def complete(self, module: Module) -> None:
        """Signals that the given module has complete building.

        Removes the module from the list of buildable modules and updates the
        list of now buildable modules.

        Args:
            module: The module that has finished building.
        """
        for dependent in self.deps_to_modules[module.name]:
            self.blocked_modules[dependent].remove(module.name)
            if self.blocked_modules[dependent]:
                # Still blocked on other dependencies.
                continue
            del self.blocked_modules[dependent]
            self.buildable_modules.add(dependent)
