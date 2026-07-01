# Design — Structured-tag initialization fidelity (array addressing sub-project 2)

Date: 2026-06-30
Status: Approved (design); implementation plan to follow
Branch: `project/l5k-logic-sim`

## Problem

Two classes of structured tag in the real `briles_main_rev_023.L5K` do not
initialize with fidelity:

1. **AOI-instance tags initialize as scalar `0`.** Add-On Instruction (AOI)
   types are not in the tag DB's UDT table, so `_init_type` falls through to the
   scalar default. There are **45** AOI-instance tags (`scaler_inst`,
   `clamp_max_inst`, `SCP` instances, `MisFeed` instances, …). Every `.member`
   access on them degrades, and the 37 AOI call sites in logic cannot bind real
   instance state.

2. **UDT/AOI tags carry positional aggregate initializers that are not
   decomposed into members.** `briles_special_modes := [0, 0.0, 0.0, 0.0, 0, 0,
   3.59e+002, …]` and similar (53 tags total) leave every member at its default,
   so real initial values (e.g. `359.0`) are lost.

Empirical scope check that reshaped this sub-project from the original
"array-of-UDT" framing:

- Member-after-index access already resolves (`interface.system[0].manual_prime`
  reads a real `False`) via the generic walk plus existing member-array init.
- Only one top-level UDT-array tag exists (`J_mem : Job_Memory[201]`), and its
  initializer is all zeros/empty strings — decoding it yields nothing.
- The real remaining lever is structured (AOI/UDT) tag initialization: 45 AOI
  instances at scalar `0`, and 53 tags with undecomposed aggregate initializers.

## Positional-alignment findings (verified against the real file)

- **UDT tags map 1:1 to storage members.** `briles_special_modes` has exactly 20
  storage members (members with `bit_host is None`) and its initializer has
  exactly 20 top-level items, in declaration order. Bit-overlay members consume
  no position — their value derives from the host word.
- **AOI tags pack leading BOOLs into a bitfield word.** `scaler_dint` has 8
  parameters (`EnableIn, EnableOut, in, in_min, in_max, out_min, out_max, out`)
  but its initializer `[3,0,0,100,0,5000,0]` has 7 items: the two leading BOOLs
  collapse into the leading bitfield item `3` (bits 0,1). This packing is fiddly,
  and the parameter *values* only matter once the AOI executes.

## Decisions

1. **Scope: UDT aggregate decomposition now, AOI value decomposition deferred.**
   UDT-tag positional decomposition is clean (verified 1:1) and its members are
   read directly by ladder logic, so it has immediate, realized value. AOI-tag
   value decomposition depends on the leading-bitfield packing and only pays off
   once AOIs execute, so it is deferred to sub-project 3 (AOI invocation), where
   the packing semantics fit naturally. AOI-instance tags still gain *structural*
   init here (members exist as per-parameter defaults).

2. **Bit-overlay members derive from the host word at init time.** After storage
   members are assigned, each bit-overlay member is set from the corresponding
   bit of its host word's initialized value. This is a one-time init derivation,
   not runtime coherence, and resolves the Plan 4 bit/word gap for initial state.

3. **Standard library only; degrade, never crash** — consistent with the rest of
   the project.

## Components

### 1. AOI-instance tag init — `src/l5k_sim/tagdb.py`

- `TagDatabase` gains `self._aois: dict[str, list[Tag]]`, populated in
  `from_project` from `project.controller.aois` as `{aoi.name: aoi.parameters}`.
- `_init_type` gains an AOI branch (alongside the UDT branch): when `data_type`
  is a key in `self._aois`, return
  `{p.name: self._init_type(p.data_type, p.initial) for p in self._aois[data_type]}`.
  Parameters initialize from their own declared `initial` when present, else the
  type default. AOI-instance aggregate *values* are not applied here (deferred).

### 2. UDT-tag positional aggregate decomposition — `src/l5k_sim/tagdb.py`

New helper `_init_struct(self, data_type, initial) -> dict`:

- Build the default member dict exactly as the current UDT branch does
  (bit-overlay members → `False`, array members → list, scalars/nested via
  `_init_type`).
- If `initial` is an aggregate `[...]`, strip the brackets, split top-level items
  with `split_top_level`, and walk the members in declaration order:
  - Skip bit-overlay members (`bit_host is not None`) — they consume no position.
  - For each storage member, consume the next item:
    - array member (`dim` set) → the item is a nested `[...]`; assign
      `_init_array(elem_type, dim, item)`.
    - nested UDT member (type in `self._udts`) → the item is a nested `[...]`;
      assign `_init_struct(member_type, item)`.
    - scalar member → assign `_init_type(member_type, item)` (coerces per type,
      including `2#` binary and the existing literal forms).
  - If items run out before members, remaining members keep their defaults; if
    items exceed storage members, append a diagnostic and stop.
- After assignment, derive bit-overlay members: for each member with
  `bit_host` set, assign `bool((int(host_value) >> bit_pos) & 1)` using the
  initialized value of the host storage member.

Wire the UDT branch of `_init_type` to return `self._init_struct(data_type,
initial)`. Because `_init_array` already passes each element's item as its
`initial` to `_init_type(elem_type, item)`, nested UDT-array elements decompose
recursively with no extra code (covers `J_mem`).

### 3. Instructions and engine

No changes. Reads/writes resolve member paths through the existing walk; this
sub-project only changes how initial member values are populated.

## Data flow

`from_project` builds `self._udts` and `self._aois` → each tag's `_init_value`
calls `_init_type(data_type, initial)` → AOI types build a parameter dict; UDT
types build a member dict via `_init_struct`, applying the aggregate initializer
positionally and deriving bit-overlay members → member reads at scan time return
the initialized values.

## Error handling

- Aggregate item count ≠ storage member count → assign what aligns, append a
  diagnostic for the remainder, never raise.
- Non-literal item for a scalar member → keep the member default.
- Malformed aggregate (not bracketed, unbalanced) → return defaults, append a
  diagnostic.
- Unknown host member for a bit overlay → leave the bit at its default `False`.

## Testing strategy

TDD, one failing test per behavior.

- **AOI init:** a tag whose type is an AOI initializes to a dict keyed by the
  AOI's parameter names, each at its type default.
- **UDT decomposition:** a UDT with a SINT host, two bit overlays, and a REAL
  member, initialized `[3, 25.5]`, yields host `3`, bit-0 member `True`, bit-1
  member `True`, REAL member `25.5`.
- **Bit derivation:** the bit-overlay members reflect the host word's initialized
  bits.
- **Nested:** a UDT with a nested UDT member or an array member decomposes
  recursively from a nested aggregate.
- **Mismatch:** an initializer with more items than storage members appends a
  diagnostic and does not raise.
- **Guarded real-file regression** (`skipif` on the local Briles path): a known
  `briles_special_modes` member receives its real initial value (the `359.0`
  position), a `scaler_inst`-style AOI instance reads as a dict, and scanning
  does not crash.

The full suite (currently 108 passing) must stay green.

## Known limitations (documented, deferred)

- AOI-instance aggregate *value* decomposition (leading-bitfield-packed BOOLs) —
  sub-project 3 (AOI invocation).
- AOI *execution* (binding parameters and running the AOI Logic routine) —
  sub-project 3.
- `J_mem`'s deep initializer decodes structurally but to all-zero/empty values
  (no meaningful state to recover).
