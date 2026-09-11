# Q4 independent development exploration

Local synthetic random Q4 seeds 2026094400–2026094407, spatial noise,
latest main configuration (triangular coverage). Each run cleared all sources.
These eight development cases are not holdout or official measurements.

| Variant | Mean seconds/source | Maximum |
|---|---:|---:|
| main shared |705.5326|938.5507|
| mixed, regional supporting halfplanes, 200/100 second station |628.9299|831.2587|
| mixed 350/150 |640.0731|829.8396|
| mixed 500/200 |638.7616|830.4676|
| mixed 100/75 |636.3390|835.4118|
| fixed open 2-opt survey order + mixed 200/100 |657.2735|862.8015|
| fixed route, insertion detour threshold 100m |732.7179|929.5547|
| fixed route, insertion detour threshold 300m |699.7833|879.6855|
| fixed route, insertion detour threshold 600m |659.5921|823.0420|
| mixed + maximum 1 refinement |637.0024|832.7848|
| mixed + maximum 2 refinements |654.5301|832.7848|
| mixed + maximum 3 refinements |653.8032|832.7848|

Refinement first mirrors the last station about the original bearing when no
second direction was obtained; otherwise measures at the polygon center plus
alternating 75m lateral offsets. Original optical fallback remains finite.

No prototype excludes any region based on no_signal. Mixed routing retains
all original triangular survey points, preserving directed half-disk coverage.
The prototype imports production geometry, simulator, and final optical clear.
Production code was not edited. Remaining opportunity is reducing coverage
stations / total survey length; route movement dominates these experiments.
