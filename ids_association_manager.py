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
    High-performance manager for associations between identifiers.
    
    Modes:
    - Default: One-to-Many (One A can have multiple Bs).
    - Single Mode: One-to-One (One A can have at most one B).
    
    Structure:
    - Type A objects (id_a) can be an `int` or a `tuple` of ints.
    - Type B objects (id_b) are strictly `int`.
    - Type B IDs are managed within a defined pool.
    
    Performance:
    - All critical operations are O(1).
    - Accessors return immutable collections (frozenset).
    """
    
    __slots__ = ('_free_bs', '_b_to_a', '_a_to_bs', '_single_mode')

    def __init__(self, max_b_ids: Union[int, Iterable[int]], single_mode: bool = False):
        """
        Initialize the manager.

        Args:
            max_b_ids: Initial pool of B IDs (int count or iterable).
            single_mode: If True, enforces that an A ID can only have ONE B ID at a time.
                         Assigning a new B to an A will auto-release the previous B.
        """
        if isinstance(max_b_ids, int):
            self._free_bs: Set[int] = set(range(max_b_ids))
        else:
            self._free_bs: Set[int] = set(max_b_ids)
            
        self._b_to_a: Dict[int, ID_A_TYPE] = {}
        self._a_to_bs: Dict[ID_A_TYPE, Set[int]] = {}
        self._single_mode = single_mode

    def associate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """
        Associates one or more B IDs to an A ID.
        
        If single_mode is True:
        - Only one B ID can be passed (raises ValueError if list with len > 1).
        - Any existing association for id_a is removed (the old B is freed/dissociated)
          before adding the new one.
        """
        # Normalize input
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        # SINGLE MODE CHECK
        if self._single_mode:
            if len(targets) > 1:
                raise ValueError("In single_mode, you can only associate one B ID at a time.")
            
            # If A already has a B, release it first!
            if id_a in self._a_to_bs:
                existing_bs = list(self._a_to_bs[id_a]) # Copy to avoid iteration issues
                for old_b in existing_bs:
                    self.remove_b(old_b) # This frees old_b back to pool or just unlinks it

        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Case 1: B is already assigned elsewhere -> Steal it
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                if old_a == id_a:
                    continue # Already linked correctly
                
                # Disconnect from old parent
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set:
                    del self._a_to_bs[old_a]
            
            # Case 2: B is free -> Take from pool
            elif b_id in self._free_bs:
                self._free_bs.remove(b_id)
            
            # Link new
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: ID_A_TYPE) -> int:
        """
        Allocates a free B ID to A.
        In single_mode, releases any existing B associated with A first.
        """
        # SINGLE MODE CHECK
        if self._single_mode:
            if id_a in self._a_to_bs:
                existing_bs = list(self._a_to_bs[id_a])
                for old_b in existing_bs:
                    self.remove_b(old_b)

        if not self._free_bs:
            raise MemoryError("No free B IDs available.")
        
        b_id = self._free_bs.pop()
        
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
            
        self._b_to_a[b_id] = id_a
        self._a_to_bs[id_a].add(b_id)
        
        return b_id

    def remove_a(self, id_a: ID_A_TYPE) -> None:
        """Removes A and releases all its Bs."""
        if id_a in self._a_to_bs:
            bs_to_free = self._a_to_bs.pop(id_a)
            for b_id in bs_to_free:
                del self._b_to_a[b_id]
                self._free_bs.add(b_id)

    def remove_b(self, id_b: int) -> None:
        """Removes specific B."""
        if id_b in self._b_to_a:
            old_a = self._b_to_a.pop(id_b)
            parent_set = self._a_to_bs[old_a]
            parent_set.remove(id_b)
            if not parent_set:
                del self._a_to_bs[old_a]
            self._free_bs.add(id_b)
        elif id_b not in self._free_bs:
             self._free_bs.add(id_b)

    # --- Accessors ---
    
    def get_bs(self, id_a: ID_A_TYPE) -> FrozenSet[int]:
        return frozenset(self._a_to_bs.get(id_a, ()))

    def get_a(self, id_b: int) -> Optional[ID_A_TYPE]:
        return self._b_to_a.get(id_b)

    def get_all_active_a(self) -> FrozenSet[ID_A_TYPE]:
        return frozenset(self._a_to_bs.keys())

    def get_all_active_b(self) -> FrozenSet[int]:
        return frozenset(self._b_to_a.keys())

    @property
    def count_free(self) -> int:
        return len(self._free_bs)

    # --- Representation Methods ---

    def __repr__(self) -> str:
        """Developer-friendly string representation."""
        mode = "Single" if self._single_mode else "Multi"
        return (f"<IDsAssociationManager(mode={mode}, "
                f"active_a={len(self._a_to_bs)}, "
                f"free_b={len(self._free_bs)})>")

    def __str__(self) -> str:
        """User-friendly string showing current map."""
        lines = [f"IDsAssociationManager (Mode: {'Single' if self._single_mode else 'Multi'})"]
        lines.append(f"Free IDs: {len(self._free_bs)}")
        lines.append("Associations:")
        if not self._a_to_bs:
            lines.append("  (Empty)")
        else:
            # Sort for deterministic display if keys are sortable, else arbitrary order
            try:
                sorted_keys = sorted(self._a_to_bs.keys(), key=lambda x: str(x))
            except Exception:
                sorted_keys = list(self._a_to_bs.keys())

            for a in sorted_keys:
                bs = sorted(list(self._a_to_bs[a]))
                lines.append(f"  {a} -> {bs}")
        return "
".join(lines)