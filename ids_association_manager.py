"""
IDsAssociationManager
A high-performance, single-file Python utility library for managing dynamic **One-to-Many** associations between integer identifiers.
Designed for efficiency, it handles allocation, re-assignment, and cleanup of ID linkages in **O(1)** time complexity.
"""

from typing import Set, Dict, Optional, List, Union, Iterable

class IDsAssociationManager:
    """
    High-performance manager for N-N (One-to-Many) associations between integer IDs.
    
    Designed to handle associations where:
    - Type A objects (id_a) can have multiple Type B objects (id_b).
    - Type B objects (id_b) belong to at most one Type A object (exclusive ownership).
    - Type B IDs are managed within a defined pool (allocation/release).
    
    Performance:
    - All critical operations (associate, allocate, remove) are O(1).
    - Optimized for int-to-int mappings using Python's native hash tables.
    """
    
    __slots__ = ('_free_bs', '_b_to_a', '_a_to_bs')

    def __init__(self, max_b_ids: Union[int, Iterable[int]]):
        """
        Initialize the association manager with a pool of available B IDs.

        Args:
            max_b_ids: 
                - If int: creates a pool of IDs from 0 to max_b_ids - 1.
                - If Iterable[int]: uses the provided integers as the pool.
        """
        if isinstance(max_b_ids, int):
            self._free_bs: Set[int] = set(range(max_b_ids))
        else:
            self._free_bs: Set[int] = set(max_b_ids)
            
        # Reverse mapping: id_b -> id_a (For O(1) ownership checks)
        self._b_to_a: Dict[int, int] = {}
        
        # Forward mapping: id_a -> Set[id_b] (For O(1) group access)
        self._a_to_bs: Dict[int, Set[int]] = {}

    def associate(self, id_a: int, id_bs: Union[int, List[int]]) -> None:
        """
        Explicitly associates one or more B IDs to an A ID.
        
        Handles re-assignment automatically:
        - If a B ID is already assigned to another A, it is moved to the new A.
        - If a B ID is free, it is removed from the free pool.

        Args:
            id_a: The ID of the Type A object (owner).
            id_bs: A single int or a list of ints representing Type B objects to associate.
        """
        # Normalize input to always be iterable, avoiding list creation overhead for single int
        targets = (id_bs,) if isinstance(id_bs, int) else id_bs

        # Ensure A entry exists
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
        
        target_set = self._a_to_bs[id_a]

        for b_id in targets:
            # Case 1: B is already assigned (possibly to another A)
            if b_id in self._b_to_a:
                old_a = self._b_to_a[b_id]
                
                # If already assigned to current A, skip
                if old_a == id_a:
                    continue 
                
                # Disconnect from old parent (Inline logic for speed)
                old_set = self._a_to_bs[old_a]
                old_set.remove(b_id)
                if not old_set:
                    del self._a_to_bs[old_a]
            
            # Case 2: B is free -> Take it from pool
            elif b_id in self._free_bs:
                self._free_bs.remove(b_id)
            
            # Case 3: B is unknown (neither free nor assigned)
            # By default we accept it (permissive mode), but could raise ValueError here.
            
            # Create new link
            self._b_to_a[b_id] = id_a
            target_set.add(b_id)

    def allocate(self, id_a: int) -> int:
        """
        Automatically allocates a free B ID to the specified A ID.

        Args:
            id_a: The ID of the Type A object requesting a resource.

        Returns:
            int: The allocated B ID.

        Raises:
            MemoryError: If no B IDs are available in the free pool.
        """
        if not self._free_bs:
            raise MemoryError("No free B IDs available in the pool.")
        
        # Pop an arbitrary free ID (O(1))
        b_id = self._free_bs.pop()
        
        if id_a not in self._a_to_bs:
            self._a_to_bs[id_a] = set()
            
        self._b_to_a[b_id] = id_a
        self._a_to_bs[id_a].add(b_id)
        
        return b_id

    def remove_a(self, id_a: int) -> None:
        """
        Removes a Type A object (obsolete).
        All associated B objects are released back to the free pool.

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
        Removes a specific Type B object (obsolete).
        Updates the corresponding Type A object and returns the ID to the free pool.

        Args:
            id_b: The ID of the Type B object to remove.
        """
        if id_b in self._b_to_a:
            old_a = self._b_to_a.pop(id_b)
            parent_set = self._a_to_bs[old_a]
            parent_set.remove(id_b)
            
            # Clean up A if it has no more Bs
            if not parent_set:
                del self._a_to_bs[old_a]
                
            self._free_bs.add(id_b)
            
        # If B is already in free pool or unknown, do nothing (idempotent)
        elif id_b not in self._free_bs:
             self._free_bs.add(id_b)

    # --- Accessors / Inspection ---
    
    def get_bs(self, id_a: int) -> Set[int]:
        """Returns the set of B IDs associated with A (empty set if none)."""
        return self._a_to_bs.get(id_a, set())

    def get_a(self, id_b: int) -> Optional[int]:
        """Returns the A ID owning the given B ID (None if B is free/unknown)."""
        return self._b_to_a.get(id_b)
        
    @property
    def count_free(self) -> int:
        """Returns the number of currently available B IDs."""
        return len(self._free_bs)
