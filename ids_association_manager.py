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

from typing import Set, Dict, Optional, List, Union, Iterable

class AssociationManager:
    """
    Efficiently manages One-to-Many associations between integer IDs.
    
    Optimized for performance with large datasets (10k+ items) using
    native Python sets and dictionaries for O(1) time complexity.
    """
    
    # Use __slots__ to freeze class structure and prevent dynamic attribute creation
    __slots__ = ('_free_bs', '_b_to_a', '_a_to_bs')

    def __init__(self, max_b_ids: Union[int, Iterable[int]]):
        """
        Initialize the manager with a pool of Type B IDs.

        Args:
            max_b_ids: Either an integer N (creating a pool of IDs from 0 to N-1)
                       or an iterable of specific integer IDs to use as the pool.
        """
        if isinstance(max_b_ids, int):
            self._free_bs: Set[int] = set(range(max_b_ids))
        else:
            self._free_bs: Set[int] = set(max_b_ids)
            
        # Reverse mapping: Maps a B_ID to its owner A_ID.
        # Allows instant O(1) lookup of an item's current owner.
        self._b_to_a: Dict[int, int] = {}
        
        # Direct mapping: Maps an A_ID to a set of its associated B_IDs.
        # Allows instant O(1) access to all items owned by A.
        self._a_to_bs: Dict[int, Set[int]] = {}

    def associate(self, id_a: int, id_bs: Union[int, List[int]]) -> None:
        """
        Manually associate one or more Type B IDs to a Type A ID.
        
        If a provided B ID is already associated with another A ID, it will be
        automatically unlinked from the old owner and linked to the new one.

        Args:
            id_a: The ID of the Type A object (owner).
            id_bs: A single integer ID or a list of integer IDs of Type B (items).
        """
        # Optimization: Tuple creation is faster than list for single items
        if isinstance(id_bs, int):
            targets = (id_bs,)
        else:
            targets = id_bs

        # Ensure the owner entry exists in the direct mapping
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Case 1: B is already used -> Steal it from the old owner
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                
                # If already associated with this A, skip to save cycles
                if old_a == id_a:
                    continue 
                
                # Disconnect from old parent efficiently
                # We know old_a exists because b_id was in _b_to_a
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set:
                    del self._a_to_bs[old_a]
            
            # Case 2: B is free -> Take it from the pool
            elif b_id in self._free_bs:
                self._free_bs.remove(b_id)
            
            # Case 3: B is unknown (not in pool, not used)
            # Current behavior: Accept it silently (permissive mode).
            # To be strict, one could raise a ValueError here.
            
            # Establish the new link
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: int) -> int:
        """
        Automatically allocate a free Type B ID to a Type A object.

        Args:
            id_a: The ID of the Type A object requesting an association.

        Returns:
            The allocated Type B ID.

        Raises:
            MemoryError: If no Type B IDs are available in the free pool.
        """
        if not self._free_bs:
            raise MemoryError("No more Type B IDs available in the pool.")
        
        # Pop is O(1) for sets
        b_id = self._free_bs.pop()
        
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
            
        self._b_to_a[b_id] = id_a
        self._a_to_bs[id_a].add(b_id)
        
        return b_id

    def remove_a(self, id_a: int) -> None:
        """
        Remove a Type A object (obsolete).
        All associated Type B IDs are released back to the free pool.

        Args:
            id_a: The ID of the Type A object to remove.
        """
        if id_a in self._a_to_bs:
            bs_to_free = self._a_to_bs.pop(id_a)
            for b_id in bs_to_free:
                del self._b_to_a[b_id]
                self._free_bs.add(b_id)

    def remove_b(self, id_b: int) -> None:
        """
        Remove/Release a specific Type B ID (obsolete or reset).
        The ID is returned to the free pool.

        Args:
            id_b: The ID of the Type B object to release.
        """
        if id_b in self._b_to_a:
            old_a = self._b_to_a.pop(id_b)
            parent_set = self._a_to_bs[old_a]
            parent_set.remove(id_b)
            
            # Cleanup parent if it has no more children
            if not parent_set:
                del self._a_to_bs[old_a]
                
            self._free_bs.add(id_b)
        elif id_b not in self._free_bs:
             # Logic for "unknown" IDs that were forcibly added via associate()
             # If we want to recycle them, we add them to free_bs here.
             self._free_bs.add(id_b)

    # --- Utility Accessors ---
    
    def get_bs(self, id_a: int) -> Set[int]:
        """
        Retrieve all Type B IDs associated with a specific Type A ID.
        
        Returns:
            A set of Type B IDs (empty set if no association exists).
        """
        return self._a_to_bs.get(id_a, set())

    def get_a(self, id_b: int) -> Optional[int]:
        """
        Retrieve the Type A ID that owns the specific Type B ID.
        
        Returns:
            The owner Type A ID, or None if the B ID is free/unknown.
        """
        return self._b_to_a.get(id_b)
        
    @property
    def count_free(self) -> int:
        """Returns the number of available Type B IDs in the pool."""
        return len(self._free_bs)
