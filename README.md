# IDsAssociationManager

A high-performance, single-file Python utility library for managing dynamic **One-to-Many** or **One-to-One** associations between integer identifiers.

Designed for efficiency, it handles allocation, re-assignment, and cleanup of ID linkages in **O(1)** or **O(log N)** time complexity depending on the chosen mode.

## Features

- **High Performance**: Built on Python's native `dict` and `set` structures.
- **Dual Allocation Strategy**:
  - **Unordered Mode** (Default): Ultra-fast **O(1)** allocation (arbitrary ID).
  - **Ordered Mode**: Deterministic allocation (Smallest ID first) using `bisect` (**O(log N)**).
- **Flexible Keys**: Supports both `int` and `tuple` of `int` as parent identifiers (ID A).
- **Single Mode (1-to-1)**: Optional enforcement of exclusive one-to-one relationships (auto-releases previous ID upon new allocation).
- **Dynamic Re-assignment**: Automatically handles ownership transfer (stealing).
- **Memory Efficient**: Optimized for integer IDs with negligible memory footprint.
- **Type Safety**: Strictly typed to maximize interpreter optimization.

## Usage

### 1. Initialization

Initialize the manager with a pool of available IDs (Type B).

```python
from ids_association_manager import IDsAssociationManager

# Standard Mode: O(1) speed, arbitrary allocation order
mgr = IDsAssociationManager(10000)

# Ordered Mode: Always allocates the smallest available ID (e.g. 0, then 1...)
mgr_ordered = IDsAssociationManager(10000, ordered=True)

# Single Mode: Enforces 1-to-1 relationship
mgr_single = IDsAssociationManager(10000, single_mode=True)
```

### 2. Manual Association

Link specific B IDs to an A ID. If a B ID was already assigned elsewhere, it is moved automatically.

```python
# Associate IDs 10 and 20 to object A=1
mgr.associate(id_a=1, id_bs=[10, 20])

# Supports Tuple keys for complex identifiers
mgr.associate(id_a=(12, 45), id_bs=30)
```

### 3. Automatic Allocation

Request a free B ID from the pool for a specific A ID.

```python
try:
    # Allocates a free ID to A=1
    new_b_id = mgr.allocate(id_a=1)
    print(f"Allocated B ID: {new_b_id}")
except MemoryError:
    print("No more IDs available in the pool!")
```

### 4. Single Mode Behavior

If initialized with `single_mode=True`, the manager ensures an A ID holds only one B ID at a time.

```python
mgr_single.allocate(100) # Allocates ID 0 to A=100
print(mgr_single.get_bs(100)) # {0}

mgr_single.allocate(100) # Allocates ID 1 to A=100, and AUTO-FREES ID 0
print(mgr_single.get_bs(100)) # {1}
```

### 5. Inspection & Cleanup

```python
# Get all B IDs for A=2 (Returns a frozenset)
bs = mgr.get_bs(2)

# Find owner of B=10
owner = mgr.get_a(10)

# Get all active parents
active_parents = mgr.get_all_active_a()

# Cleanup: Release resources
mgr.remove_a(id_a=1)      # Free all IDs held by A=1
mgr.remove_b(id_b=20)     # Free specific ID 20
```

## Performance Note

- **Unordered Mode**: Allocation/Deletion is **O(1)**. Ideal for massive pools (1M+ items) where order doesn't matter.
- **Ordered Mode**: Allocation is **O(N)** (amortized) due to list operations, but highly optimized with `bisect`. Ideal for typical usage (up to 100k items) where deterministic behavior is preferred.

## License

MIT License. Free to use in personal and commercial projects.