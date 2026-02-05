#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IDs Association Managers
------------------------
High-performance managers for associations between identifiers.

Classes:
- IDsAssociationManager: Exclusive associations (One B can only belong to one A)
- IDsManyToManyManager: Non-exclusive associations (One B can be shared by multiple A)

Author: Arnaud Pessel
Email: pessel.arnaud@gmail.com
GitHub: https://github.com/Dunaar
Copyright (c) 2026 Arnaud Pessel. All rights reserved.
License: MIT
"""

import bisect
from typing import Set, Dict, Optional, List, Union, Iterable, Tuple, FrozenSet

# Type alias for ID A (can be an int or a tuple of ints)
ID_A_TYPE = Union[int, Tuple[int, ...]]


# ============================================================================
# EXCLUSIVE ASSOCIATIONS (One-to-Many with exclusivity)
# ============================================================================

class IDsAssociationManager:
    """
    Manager for EXCLUSIVE One-to-Many associations.
    
    Key behavior:
    - One A can have multiple Bs.
    - One B belongs to AT MOST one A (exclusive ownership).
    - Associating a B that already belongs to another A will "steal" it.
    
    Modes:
    - ordered: Allocates smallest IDs first (deterministic).
    - single_mode: Enforces 1-to-1 relationship with idempotent allocation.
    """
    
    __slots__ = ('_free_pool', '_b_to_a', '_a_to_bs', '_single_mode', '_ordered')

    def __init__(self, max_b_ids: Union[int, Iterable[int]], single_mode: bool = False, ordered: bool = False):
        """
        Initialize the manager.

        Args:
            max_b_ids: Pool size (int) or specific IDs (iterable).
            single_mode: Enforce 1-to-1 relationship.
            ordered: True for deterministic allocation (smallest ID first).
        """
        if isinstance(max_b_ids, int):
            if max_b_ids <= 0:
                raise ValueError("max_b_ids must be > 0")
            initial_ids = range(max_b_ids)
        else:
            initial_ids = list(max_b_ids)
            if not initial_ids:
                raise ValueError("ID pool cannot be empty")
        
        self._single_mode = single_mode
        self._ordered = ordered
        
        if self._ordered:
            self._free_pool = sorted(list(initial_ids))
        else:
            self._free_pool = set(initial_ids)
            
        self._b_to_a: Dict[int, ID_A_TYPE] = {}
        self._a_to_bs: Dict[ID_A_TYPE, Set[int]] = {}

    def associate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """Associates one or more B IDs to an A ID (exclusive: steals if needed)."""
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        if self._single_mode:
            if len(targets) > 1:
                raise ValueError("Single mode active: cannot associate multiple IDs.")
            if id_a in self._a_to_bs:
                for old_b in list(self._a_to_bs[id_a]):
                    self.remove_b(old_b)

        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                if old_a == id_a: continue
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set: del self._a_to_bs[old_a]
            else:
                if self._ordered:
                    idx = bisect.bisect_left(self._free_pool, b_id)
                    if idx < len(self._free_pool) and self._free_pool[idx] == b_id:
                        self._free_pool.pop(idx)
                else:
                    if b_id in self._free_pool:
                        self._free_pool.remove(b_id)
            
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: ID_A_TYPE, force: bool = False) -> int:
        """Allocates a B ID to id_a (idempotent in single_mode unless force=True)."""
        if self._single_mode and id_a in self._a_to_bs:
            if not force:
                return next(iter(self._a_to_bs[id_a]))
            for old_b in list(self._a_to_bs[id_a]):
                self.remove_b(old_b)

        if not self._free_pool:
            raise MemoryError("No free B IDs available.")
        
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
        """Internal helper to return ID to pool."""
        if self._ordered:
            if check_duplicates:
                idx = bisect.bisect_left(self._free_pool, b_id)
                if idx == len(self._free_pool) or self._free_pool[idx] != b_id:
                    bisect.insort(self._free_pool, b_id)
            else:
                bisect.insort(self._free_pool, b_id)
        else:
            self._free_pool.add(b_id)

    def get_bs(self, id_a: ID_A_TYPE) -> Union[FrozenSet[int], Optional[int]]:
        """Returns B IDs for A (int in single_mode, frozenset otherwise)."""
        if self._single_mode:
            bs = self._a_to_bs.get(id_a)
            if bs:
                return next(iter(bs))
            return None
        else:
            return frozenset(self._a_to_bs.get(id_a, ()))
    
    def get_a(self, id_b: int) -> Optional[ID_A_TYPE]:
        """Returns the A ID owning B (exclusive)."""
        return self._b_to_a.get(id_b)

    def get_all_active_a(self) -> FrozenSet[ID_A_TYPE]:
        """Returns all A IDs with associations."""
        return frozenset(self._a_to_bs.keys())

    def get_all_active_b(self) -> FrozenSet[int]:
        """Returns all B IDs in use."""
        return frozenset(self._b_to_a.keys())

    def has_association(self, id_a: ID_A_TYPE) -> bool:
        """Returns True if id_a has associations."""
        return id_a in self._a_to_bs and len(self._a_to_bs[id_a]) > 0

    @property
    def count_free(self) -> int:
        """Returns available B IDs count."""
        return len(self._free_pool)

    @property
    def is_empty(self) -> bool:
        """Returns True if no associations exist."""
        return len(self._a_to_bs) == 0

    def clear(self) -> None:
        """Removes all associations and resets pool."""
        all_bs = set(self._b_to_a.keys())
        self._b_to_a.clear()
        self._a_to_bs.clear()
        
        if self._ordered:
            self._free_pool = sorted(list(all_bs) + list(self._free_pool))
        else:
            self._free_pool.update(all_bs)

    def __str__(self) -> str:
        lines = [f"IDsAssociationManager (Mode: {'Single' if self._single_mode else 'Multi'}, Ordered: {self._ordered})"]
        lines.append(f"Free IDs: {len(self._free_pool)}")
        
        if self._free_pool:
            next_val = self._free_pool[0] if self._ordered else next(iter(self._free_pool))
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
        return f"<IDsAssociationManager(mode={'Single' if self._single_mode else 'Multi'}, ordered={self._ordered}, free={len(self._free_pool)})>"


# ============================================================================
# NON-EXCLUSIVE ASSOCIATIONS (Many-to-Many)
# ============================================================================

class IDsManyToManyManager:
    """
    Manager for NON-EXCLUSIVE Many-to-Many associations.
    
    Key behavior:
    - One A can have multiple Bs.
    - One B can be SHARED by multiple As (non-exclusive).
    - No "stealing" behavior.
    """
    
    __slots__ = ('_free_pool', '_b_to_as', '_a_to_bs', '_ordered')

    def __init__(self, max_b_ids: Union[int, Iterable[int]], ordered: bool = False):
        """
        Initialize the manager.

        Args:
            max_b_ids: Pool size (int) or specific IDs (iterable).
            ordered: True for deterministic allocation (smallest ID first).
        """
        if isinstance(max_b_ids, int):
            if max_b_ids <= 0:
                raise ValueError("max_b_ids must be > 0")
            initial_ids = range(max_b_ids)
        else:
            initial_ids = list(max_b_ids)
            if not initial_ids:
                raise ValueError("ID pool cannot be empty")
        
        self._ordered = ordered
        
        if self._ordered:
            self._free_pool = sorted(list(initial_ids))
        else:
            self._free_pool = set(initial_ids)
            
        self._b_to_as: Dict[int, Set[ID_A_TYPE]] = {}  # B -> Set of A
        self._a_to_bs: Dict[ID_A_TYPE, Set[int]] = {}  # A -> Set of B

    def associate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """Associates B IDs to A (non-exclusive: no stealing)."""
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Remove from free pool if needed
            if self._ordered:
                idx = bisect.bisect_left(self._free_pool, b_id)
                if idx < len(self._free_pool) and self._free_pool[idx] == b_id:
                    self._free_pool.pop(idx)
            else:
                if b_id in self._free_pool:
                    self._free_pool.remove(b_id)
            
            # Add to mappings (Many-to-Many)
            if b_id not in self._b_to_as:
                self._b_to_as[b_id] = set()
            
            self._b_to_as[b_id].add(id_a)
            target_set.add(b_id)

    def dissociate(self, id_a: ID_A_TYPE, id_bs: Union[int, List[int]]) -> None:
        """Removes specific associations between id_a and id_bs."""
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs
        
        if id_a not in self._a_to_bs:
            return
        
        for b_id in targets:
            if b_id in self._a_to_bs[id_a]:
                self._a_to_bs[id_a].remove(b_id)
            
            if b_id in self._b_to_as and id_a in self._b_to_as[b_id]:
                self._b_to_as[b_id].remove(id_a)
                
                # If B has no more associations, return to pool
                if not self._b_to_as[b_id]:
                    del self._b_to_as[b_id]
                    self._release_id(b_id)
        
        if not self._a_to_bs[id_a]:
            del self._a_to_bs[id_a]

    def allocate(self, id_a: ID_A_TYPE) -> int:
        """Allocates a free B ID to id_a."""
        if not self._free_pool:
            raise MemoryError("No free B IDs available.")
        
        if self._ordered:
            b_id = self._free_pool.pop(0)
        else:
            b_id = self._free_pool.pop()
        
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        if b_id not in self._b_to_as:
            self._b_to_as[b_id] = set()
            
        self._a_to_bs[id_a].add(b_id)
        self._b_to_as[b_id].add(id_a)
        
        return b_id

    def remove_a(self, id_a: ID_A_TYPE) -> None:
        """Removes all associations for id_a (Bs freed only if no other owners)."""
        if id_a not in self._a_to_bs:
            return
        
        bs_to_check = list(self._a_to_bs.pop(id_a))
        
        for b_id in bs_to_check:
            if b_id in self._b_to_as:
                self._b_to_as[b_id].discard(id_a)
                
                if not self._b_to_as[b_id]:
                    del self._b_to_as[b_id]
                    self._release_id(b_id)

    def remove_b(self, id_b: int) -> None:
        """Removes B from ALL associations."""
        if id_b in self._b_to_as:
            owners = list(self._b_to_as.pop(id_b))
            
            for owner_a in owners:
                if owner_a in self._a_to_bs:
                    self._a_to_bs[owner_a].discard(id_b)
                    if not self._a_to_bs[owner_a]:
                        del self._a_to_bs[owner_a]
            
            self._release_id(id_b)
        else:
            self._release_id(id_b, check_duplicates=True)

    def _release_id(self, b_id: int, check_duplicates: bool = False) -> None:
        """Internal helper to return ID to pool."""
        if self._ordered:
            if check_duplicates:
                idx = bisect.bisect_left(self._free_pool, b_id)
                if idx == len(self._free_pool) or self._free_pool[idx] != b_id:
                    bisect.insort(self._free_pool, b_id)
            else:
                bisect.insort(self._free_pool, b_id)
        else:
            self._free_pool.add(b_id)

    def get_bs(self, id_a: ID_A_TYPE) -> FrozenSet[int]:
        """Returns B IDs associated with A."""
        return frozenset(self._a_to_bs.get(id_a, ()))
    
    def get_as(self, id_b: int) -> FrozenSet[ID_A_TYPE]:
        """Returns A IDs associated with B (Many-to-Many)."""
        return frozenset(self._b_to_as.get(id_b, ()))

    def has_association(self, id_a: ID_A_TYPE, id_b: int) -> bool:
        """Checks if a specific association exists."""
        return id_a in self._a_to_bs and id_b in self._a_to_bs[id_a]

    def get_all_active_a(self) -> FrozenSet[ID_A_TYPE]:
        """Returns all A IDs with associations."""
        return frozenset(self._a_to_bs.keys())

    def get_all_active_b(self) -> FrozenSet[int]:
        """Returns all B IDs in use."""
        return frozenset(self._b_to_as.keys())

    @property
    def count_free(self) -> int:
        """Returns available B IDs count."""
        return len(self._free_pool)

    @property
    def is_empty(self) -> bool:
        """Returns True if no associations exist."""
        return len(self._a_to_bs) == 0

    def clear(self) -> None:
        """Removes all associations and resets pool."""
        all_bs = set(self._b_to_as.keys())
        self._b_to_as.clear()
        self._a_to_bs.clear()
        
        if self._ordered:
            self._free_pool = sorted(list(all_bs) + list(self._free_pool))
        else:
            self._free_pool.update(all_bs)

    def __str__(self) -> str:
        lines = [f"IDsManyToManyManager (Ordered: {self._ordered})"]
        lines.append(f"Free IDs: {len(self._free_pool)}")
        
        if self._free_pool:
            next_val = self._free_pool[0] if self._ordered else next(iter(self._free_pool))
        else:
            next_val = "None"
        lines.append(f"Next Allocation: {next_val}")
        
        lines.append("\nA -> B Associations:")
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
        
        lines.append("\nB -> A Reverse Map:")
        if not self._b_to_as:
            lines.append("  (Empty)")
        else:
            for b in sorted(self._b_to_as.keys()):
                as_list = sorted(list(self._b_to_as[b]), key=lambda x: str(x))
                lines.append(f"  {b} <- {as_list}")
                
        return "\n".join(lines)
        
    def __repr__(self) -> str:
        return f"<IDsManyToManyManager(ordered={self._ordered}, active_a={len(self._a_to_bs)}, active_b={len(self._b_to_as)}, free={len(self._free_pool)})>"


# ============================================================================
# TESTS
# ============================================================================

def main():
    print("=" * 70)
    print("EXCLUSIVE MANAGER (IDsAssociationManager) - Tests")
    print("=" * 70 + "\n")

    print("--- Test 1: Exclusive Stealing ---")
    mgr_excl = IDsAssociationManager(10, ordered=True)
    mgr_excl.associate(1, 5)
    mgr_excl.associate(2, 5)  # Steals 5 from A=1
    print(f"A=1 has: {mgr_excl.get_bs(1)}")
    print(f"A=2 has: {mgr_excl.get_bs(2)}")
    print(f"B=5 owned by: {mgr_excl.get_a(5)}")
    assert len(mgr_excl.get_bs(1)) == 0
    print("✓ Pass\n")

    print("--- Test 2: Single Mode Idempotency ---")
    mgr_single = IDsAssociationManager(5, single_mode=True, ordered=True)
    id1 = mgr_single.allocate(10)
    id2 = mgr_single.allocate(10)
    assert id1 == id2
    id3 = mgr_single.allocate(10, force=True)
    print(f"Idempotent: {id1}, Forced: {id3}")
    print("✓ Pass\n")

    print("=" * 70)
    print("NON-EXCLUSIVE MANAGER (IDsManyToManyManager) - Tests")
    print("=" * 70 + "\n")

    print("--- Test 3: Non-Exclusive Sharing ---")
    mgr_share = IDsManyToManyManager(10, ordered=True)
    mgr_share.associate(1, 5)
    mgr_share.associate(2, 5)  # Shares 5
    print(f"A=1 has: {mgr_share.get_bs(1)}")
    print(f"A=2 has: {mgr_share.get_bs(2)}")
    print(f"B=5 owned by: {mgr_share.get_as(5)}")
    assert 5 in mgr_share.get_bs(1)
    assert 5 in mgr_share.get_bs(2)
    print("✓ Pass\n")

    print("--- Test 4: Dissociate ---")
    mgr_share.dissociate(1, 5)
    print(f"After dissociate - A=1: {mgr_share.get_bs(1)}")
    print(f"After dissociate - B=5 owners: {mgr_share.get_as(5)}")
    assert 5 not in mgr_share.get_bs(1)
    print("✓ Pass\n")

    print("\nAll tests passed! ✓")

if __name__ == "__main__":
    main()
