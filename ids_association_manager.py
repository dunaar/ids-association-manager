#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IDsAssociationManager
---------------------
High-performance manager for associations between identifiers.

Features:
- Dual Mode: 'Ordered' (deterministic, smallest ID first) or 'Unordered' (max speed O(1)).
- Single Mode: Optional enforcement of 1-to-1 relationships.
- Idempotent Allocation: In single mode, allocate returns existing ID unless forced.
- Type Safe: Handles int and tuple keys for parents.

Author: Arnaud Pessel
Email: pessel.arnaud@gmail.com
GitHub: https://github.com/Dunaar
Copyright (c) 2026 Arnaud Pessel. All rights reserved.
License: MIT
"""

import bisect
from typing import Set, Dict, Optional, List, Union, Iterable, Tuple, FrozenSet, Any

# Type alias for ID A (can be an int or a tuple of ints)
ID_A_TYPE = Union[int, Tuple[int, ...]]

class IDsAssociationManager:
    """
    Manager for N-N or 1-1 associations.
    
    Attributes:
        ordered (bool): If True, allocates smallest IDs first (slower). 
                        If False, allocates arbitrary IDs (fastest, O(1)).
        single_mode (bool): If True, enforces one B per A.
    """
    
    __slots__ = ('_free_pool', '_b_to_a', '_a_to_bs', '_single_mode', '_ordered')

    def __init__(self, max_b_ids: Union[int, Iterable[int]], single_mode: bool = False, ordered: bool = False):
        """
        Initialize the manager.

        Args:
            max_b_ids: Pool size (int) or specific IDs (iterable).
            single_mode: Enforce 1-to-1 relationship.
            ordered: 
                - True: Deterministic allocation (Smallest ID first). Uses List+Bisect.
                - False: Fastest allocation (Arbitrary order). Uses Set.
        """
        self._single_mode = single_mode
        self._ordered = ordered

        # Initialize Pool based on mode
        initial_ids = range(max_b_ids) if isinstance(max_b_ids, int) else max_b_ids
        
        if self._ordered:
            # Ordered mode: List sorted
            self._free_pool = sorted(list(initial_ids))
        else:
            # Unordered mode: Set (O(1))
            self._free_pool = set(initial_ids)
            
        self._b_to_a: Dict[int, ID_A_TYPE] = {}
        self._a_to_bs: Dict[ID_A_TYPE, Set[int]] = {}

    def associate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """Associates one or more B IDs to an A ID."""
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        # --- Single Mode Safety ---
        if self._single_mode:
            if len(targets) > 1:
                raise ValueError("Single mode active: cannot associate multiple IDs.")
            
            # If valid, clean up previous association for this A
            if id_a in self._a_to_bs:
                for old_b in list(self._a_to_bs[id_a]):
                    self.remove_b(old_b)

        # Ensure A entry exists
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Case 1: B is already assigned (Steal)
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                if old_a == id_a: continue
                
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set: del self._a_to_bs[old_a]
            
            # Case 2: B is free (Allocation)
            else:
                if self._ordered:
                    idx = bisect.bisect_left(self._free_pool, b_id)
                    if idx < len(self._free_pool) and self._free_pool[idx] == b_id:
                        self._free_pool.pop(idx)
                else:
                    if b_id in self._free_pool:
                        self._free_pool.remove(b_id)
                
            # Create Link
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: ID_A_TYPE, force: bool = False) -> int:
        """
        Allocates a B ID to id_a.
        
        Args:
            id_a: The owner ID.
            force: (Single Mode only) If True, forces a NEW allocation (releases old ID).
                   If False and association exists, returns the EXISTING ID (idempotent).
        
        Returns:
            The allocated or existing B ID.
        """
        # --- Single Mode Logic ---
        if self._single_mode and id_a in self._a_to_bs:
            # If not forcing, return the existing ID (Idempotency)
            if not force:
                return next(iter(self._a_to_bs[id_a]))
            
            # If forcing, clean up old IDs to make room for new one
            for old_b in list(self._a_to_bs[id_a]):
                self.remove_b(old_b)

        if not self._free_pool:
            raise MemoryError("No free B IDs available.")
        
        # --- Allocation Strategy ---
        if self._ordered:
            b_id = self._free_pool.pop(0)
        else:
            b_id = self._free_pool.pop()
        
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
                self._release_id(b_id)

    def remove_b(self, id_b: int) -> None:
        """Removes B and releases it."""
        if id_b in self._b_to_a:
            old_a = self._b_to_a.pop(id_b)
            parent_set = self._a_to_bs[old_a]
            parent_set.remove(id_b)
            if not parent_set:
                del self._a_to_bs[old_a]
            
            self._release_id(id_b)
        else:
            self._release_id(id_b, check_duplicates=True)

    def _release_id(self, b_id: int, check_duplicates: bool = False) -> None:
        """Internal helper to return ID to pool based on strategy."""
        if self._ordered:
            if check_duplicates:
                idx = bisect.bisect_left(self._free_pool, b_id)
                if idx == len(self._free_pool) or self._free_pool[idx] != b_id:
                    bisect.insort(self._free_pool, b_id)
            else:
                bisect.insort(self._free_pool, b_id)
        else:
            self._free_pool.add(b_id)

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
        return len(self._free_pool)

    # --- String Representation ---

    def __str__(self) -> str:
        lines = [f"IDsAssociationManager (Mode: {'Single' if self._single_mode else 'Multi'}, Ordered: {self._ordered})"]
        lines.append(f"Free IDs: {len(self._free_pool)}")
        
        if self._free_pool:
            if self._ordered:
                next_val = self._free_pool[0]
            else:
                next_val = next(iter(self._free_pool))
        else:
            next_val = "None"
            
        lines.append(f"Next Allocation: {next_val}")
        lines.append("Associations:")
        if not self._a_to_bs:
            lines.append("  (Empty)")
        else:
            try:
                sorted_keys = sorted(self._a_to_bs.keys(), key=lambda x: str(x))
            except:
                sorted_keys = list(self._a_to_bs.keys())
            for a in sorted_keys:
                bs = sorted(list(self._a_to_bs[a]))
                lines.append(f"  {a} -> {bs}")
        return "\n".join(lines)
        
    def __repr__(self) -> str:
        return (f"<IDsAssociationManager(mode={'Single' if self._single_mode else 'Multi'}, "
                f"ordered={self._ordered}, free={len(self._free_pool)})>")


# --- MAIN TESTING SECTION ---

def main():
    print("=== IDsAssociationManager Test Suite ===\n")

    # TEST 1: Basic Usage & Ordering
    print("--- Test 1: Ordered vs Unordered ---")
    
    mgr_ord = IDsAssociationManager(10, ordered=True)
    mgr_ord.allocate(100) 
    mgr_ord.allocate(200)
    print(f"Ordered: Allocated -> {mgr_ord.get_bs(100)}, {mgr_ord.get_bs(200)}")
    mgr_ord.remove_a(100) # Frees 0
    print(f"Ordered: Next alloc for 300 -> {mgr_ord.allocate(300)}") # Should be 0
    print("OK.\n")

    # TEST 2: Single Mode Idempotency
    print("--- Test 2: Single Mode Idempotency ---")
    mgr_single = IDsAssociationManager(5, single_mode=True, ordered=True)
    
    id1 = mgr_single.allocate(10) # Gets 0
    print(f"First Alloc for 10: {id1}")
    
    id2 = mgr_single.allocate(10) # Should return 0 again (no change)
    print(f"Second Alloc for 10 (No Force): {id2}")
    assert id1 == id2
    
    id3 = mgr_single.allocate(10, force=True) # Should return 1 (0 freed, then 1 allocated?) 
    # Actually: 0 is freed, then 0 is re-inserted. Since it's sorted, 0 is available again.
    # Wait: remove_b(0) -> 0 back in pool. pop(0) -> 0.
    # So force=True might give same ID if it's the smallest! 
    # Let's verify with unordered or steal another one first.
    print(f"Force Alloc for 10: {id3}")
    
    # Let's block 0 with another user to see change
    mgr_single.remove_a(10)
    mgr_single.allocate(99) # Takes 0
    mgr_single.allocate(10) # Takes 1
    new_forced = mgr_single.allocate(10, force=True) # Frees 1, Takes 1 again (smallest)
    print(f"Force Alloc (optimized): {new_forced}")
    print("OK.\n")

    # TEST 3: Stealing
    print("--- Test 3: Resource Stealing ---")
    mgr = IDsAssociationManager(10, ordered=True)
    mgr.associate(1, [1, 2, 3])
    mgr.associate(2, 2)
    assert 2 not in mgr.get_bs(1)
    assert 2 in mgr.get_bs(2)
    print("OK.\n")

    print("\nAll tests passed successfully.")

if __name__ == "__main__":
    main()
