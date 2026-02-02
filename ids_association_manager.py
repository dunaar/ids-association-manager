#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-performance Association Manager for One-to-Many relationships.

This module provides an optimized utility class to manage evolving associations
between objects of type A and objects of type B, where both are identified by integer IDs.

Features:
- Efficient O(1) operations for associating, allocating, and removing items.
- Manages a pool of available Type B IDs.
- Enforces exclusivity: A Type B ID can be associated with at most one Type A ID.
- Automatically handles re-association (stealing) and cleanup.

Author: Arnaud Pessel
Email: pessel.arnaud@gmail.com
GitHub: https://github.com/Dunaar
Copyright (c) 2026 Arnaud Pessel. All rights reserved.
"""

from typing import Set, Dict, Optional, List, Union, Iterable, Tuple, FrozenSet

# Type alias pour id_a (int ou tuple d'ints)
ID_A_TYPE = Union[int, Tuple[int, ...]]

class IDsAssociationManager:
    """
    High-performance manager for N-N (One-to-Many) associations between identifiers.
    
    Structure:
    - Type A objects (id_a) can be an `int` or a `tuple` of ints.
    - Type B objects (id_b) are strictly `int`.
    - One A can have multiple Bs.
    - One B belongs to at most one A (exclusive ownership).
    - Type B IDs are managed within a defined pool.
    
    Performance:
    - All critical operations are O(1).
    - Accessors return immutable collections (frozenset) for safety.
    """
    
    __slots__ = ('_free_bs', '_b_to_a', '_a_to_bs')

    def __init__(self, max_b_ids: Union[int, Iterable[int]]):
        """Initialize with a pool of available B IDs."""
        if isinstance(max_b_ids, int):
            self._free_bs: Set[int] = set(range(max_b_ids))
        else:
            self._free_bs: Set[int] = set(max_b_ids)
            
        self._b_to_a: Dict[int, ID_A_TYPE] = {}
        self._a_to_bs: Dict[ID_A_TYPE, Set[int]] = {}

    def associate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """Associates one or more B IDs to an A ID."""
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Re-assignment logic
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                if old_a == id_a:
                    continue 
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set:
                    del self._a_to_bs[old_a]
            elif b_id in self._free_bs:
                self._free_bs.remove(b_id)
            
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: ID_A_TYPE) -> int:
        """Allocates a free B ID to the specified A ID."""
        if not self._free_bs:
            raise MemoryError("No free B IDs available.")
        
        b_id = self._free_bs.pop()
        
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
            
        self._b_to_a[b_id] = id_a
        self._a_to_bs[id_a].add(b_id)
        
        return b_id

    def remove_a(self, id_a: ID_A_TYPE) -> None:
        """Removes a Type A object and releases its Bs."""
        if id_a in self._a_to_bs:
            bs_to_free = self._a_to_bs.pop(id_a)
            for b_id in bs_to_free:
                del self._b_to_a[b_id]
                self._free_bs.add(b_id)

    def remove_b(self, id_b: int) -> None:
        """Removes a specific Type B object."""
        if id_b in self._b_to_a:
            old_a = self._b_to_a.pop(id_b)
            parent_set = self._a_to_bs[old_a]
            parent_set.remove(id_b)
            if not parent_set:
                del self._a_to_bs[old_a]
            self._free_bs.add(id_b)
        elif id_b not in self._free_bs:
             self._free_bs.add(id_b)

    # --- Accessors (Immutable Results) ---
    
    def get_bs(self, id_a: ID_A_TYPE) -> FrozenSet[int]:
        """Returns an immutable set of B IDs associated with A."""
        # Convert the internal set to frozenset to prevent external modification
        # Optimization: Return empty frozenset if key missing
        return frozenset(self._a_to_bs.get(id_a, ()))

    def get_a(self, id_b: int) -> Optional[ID_A_TYPE]:
        """Returns the A ID owning the given B ID."""
        return self._b_to_a.get(id_b)

    def get_all_active_a(self) -> FrozenSet[ID_A_TYPE]:
        """
        Returns an immutable set of all A IDs that currently have associations.
        Complexity: O(N_Active_A) for copy (fast enough for 10k items).
        """
        return frozenset(self._a_to_bs.keys())

    def get_all_active_b(self) -> FrozenSet[int]:
        """
        Returns an immutable set of all B IDs that are currently associated.
        Complexity: O(N_Active_B).
        """
        return frozenset(self._b_to_a.keys())

    @property
    def count_free(self) -> int:
        return len(self._free_bs)