# FloPy Comprehensive Benchmarking Plan

## Executive Summary

This document outlines a plan to expand FloPy's benchmarking capabilities to systematically track performance improvements during ongoing development, particularly the pandas-based I/O refactoring effort. The plan builds upon the existing `pytest-benchmark` infrastructure while addressing current limitations in coverage and tooling.

**Important**: These benchmarks test **FloPy code performance only**, not the runtime of MODFLOW/MODPATH executables that FloPy drives. Benchmarks focus on FloPy's I/O operations, data structure manipulations, and utility functions.

### Key Goals

1. **Quantify pandas I/O refactor impact** - Measure FloPy's file I/O performance gains
2. **Prevent performance regressions** - Automated detection of FloPy performance degradation in CI/CD
3. **Expand coverage** - Benchmark all major FloPy operations (load/write, utilities, grids, exports)
4. **Streamline workflow** - Reduce ad-hoc scripting, improve automation and reporting

## Current State Analysis

### Existing Infrastructure

**Benchmarks** (as of 2026-01-25):
- Location: `autotest/test_modflow.py:1334-1353`
- Count: 3 benchmarks
  - `test_model_init_time` - MODFLOW-2005 model initialization
  - `test_model_write_time` - Model file writing
  - `test_model_load_time` - Model file loading

**Tooling**:
- `pytest-benchmark` plugin (pyproject.toml dependency)
- Daily CI workflow (`.github/workflows/benchmark.yml`)
  - Matrix: 3 OS × 3 Python versions = 9 configurations
  - Runs: Daily at 8 AM UTC
- Post-processing: `scripts/process_benchmarks.py`
  - Generates time-series plots using seaborn
  - Outputs CSV data and PNG visualizations

### Current Limitations

1. **Narrow Coverage**
   - Only MODFLOW-2005 tested
   - No MF6, MT3D, SEAWAT coverage
   - Missing utility benchmarks (HeadFile, BudgetFile, grids, exports)

2. **Limited Visibility**
   - Results only stored as GitHub Actions artifacts
   - No historical trend tracking
   - No automated regression detection
   - Manual comparison required

3. **Workflow Issues**
   - Ad-hoc scripting for result processing
   - No integration with PR review process
   - Missing baseline comparisons

## Proposed Solution

### 1. Tooling Strategy

**Decision: Continue with pytest-benchmark + Add Codspeed Integration**

#### Rationale

- **ASV (Airspeed Velocity)**: Originally considered but now appears unmaintained
  - Major projects (NumPy, others) migrating away
  - Limited recent activity on repository

- **pytest-benchmark**: Currently working well
  - Integrated with existing test suite
  - Familiar to developers
  - Good CI integration

- **Codspeed** (RECOMMENDED ADDITION):
  - Seamless `pytest-codspeed` plugin compatibility
  - Zero-config migration from `pytest-benchmark`
  - Automated performance regression detection
  - Historical trend visualization
  - PR-based performance impact reports
  - Free for open-source projects

#### Implementation Steps

1. Add `pytest-codspeed` to test dependencies:
   ```toml
   [project.optional-dependencies]
   test = [
       # ... existing deps
       "pytest-benchmark",
       "pytest-codspeed",
   ]
   ```

2. Update benchmark workflow to use Codspeed action:
   ```yaml
   - uses: CodSpeedHQ/action@v3
     with:
       token: ${{ secrets.CODSPEED_TOKEN }}
       run: pytest autotest/benchmarks --codspeed
   ```

3. Optionally refactor existing benchmarks to use decorator pattern:
   ```python
   @pytest.mark.benchmark
   def test_model_load_time(function_tmpdir):
       model = get_perftest_model(ws=function_tmpdir, name=name)
       model.write_input()
       Modflow.load(f"{name}.nam", model_ws=function_tmpdir, check=False)
   ```

### 2. Benchmark Coverage Expansion

#### 2.1 Core I/O Benchmarks

Expand model load/write/init benchmarks across all major simulators.

**MODFLOW 6** (Highest Priority):

```python
# autotest/benchmarks/benchmark_io_mf6.py

def test_mf6_sim_init_small(benchmark, function_tmpdir):
    """Benchmark MF6 simulation initialization - small model."""
    benchmark(lambda: create_small_mf6_sim(function_tmpdir))

def test_mf6_sim_init_large(benchmark, function_tmpdir):
    """Benchmark MF6 simulation initialization - large model."""
    benchmark(lambda: create_large_mf6_sim(function_tmpdir))

def test_mf6_sim_write(benchmark, function_tmpdir):
    """Benchmark MF6 simulation write."""
    sim = create_test_mf6_sim(function_tmpdir)
    benchmark(sim.write_simulation)

def test_mf6_sim_load(benchmark, function_tmpdir):
    """Benchmark MF6 simulation load."""
    sim = create_test_mf6_sim(function_tmpdir)
    sim.write_simulation()
    sim_ws = function_tmpdir
    benchmark(lambda: MFSimulation.load(simulation_ws=sim_ws))

def test_mf6_package_write_large_arrays(benchmark, function_tmpdir):
    """Benchmark writing packages with large arrays (e.g., NPF K)."""
    sim = create_large_array_sim(function_tmpdir)
    benchmark(sim.write_simulation)

def test_mf6_multimodel_sim(benchmark, function_tmpdir):
    """Benchmark multi-model simulation I/O."""
    benchmark(lambda: create_multimodel_sim(function_tmpdir))

def test_mf6_exchange_load(benchmark, function_tmpdir):
    """Benchmark loading simulations with exchanges."""
    sim = create_exchange_sim(function_tmpdir)
    sim.write_simulation()
    benchmark(lambda: MFSimulation.load(simulation_ws=function_tmpdir))
```

**Legacy MODFLOW Variants**:

```python
# autotest/benchmarks/benchmark_io_legacy.py

@pytest.mark.parametrize("variant", ["mfnwt", "mfusg", "seawat", "mt3dms"])
def test_legacy_model_init(benchmark, function_tmpdir, variant):
    """Benchmark initialization across legacy MODFLOW variants."""
    benchmark(lambda: create_legacy_model(variant, function_tmpdir))

@pytest.mark.parametrize("grid_type", ["structured", "unstructured"])
def test_modflow_grid_types(benchmark, function_tmpdir, grid_type):
    """Benchmark I/O for different grid types."""
    benchmark(lambda: create_model_with_grid(grid_type, function_tmpdir))

@pytest.mark.parametrize("temporal", ["steady", "transient_small", "transient_large"])
def test_modflow_temporal(benchmark, function_tmpdir, temporal):
    """Benchmark I/O for different temporal discretizations."""
    benchmark(lambda: create_temporal_model(temporal, function_tmpdir))
```

#### 2.2 Post-Processing Utilities

Benchmark common workflow operations.

**HeadFile Operations**:

Note: HeadFile benchmarks use pre-existing files from examples/data directory to test FloPy's file parsing performance only, not MODFLOW runtime.

```python
# autotest/benchmarks/benchmark_utils_heads.py

from pathlib import Path
from flopy.utils import HeadFile

FREYBERG_HDS = Path("examples/data/freyberg_multilayer_transient/freyberg.hds")

@pytest.mark.skipif(not FREYBERG_HDS.exists(), reason="Example data not available")
def test_headfile_init_freyberg(benchmark):
    """Benchmark FloPy's HeadFile initialization."""
    benchmark(lambda: HeadFile(FREYBERG_HDS))

@pytest.mark.skipif(not FREYBERG_HDS.exists(), reason="Example data not available")
def test_headfile_get_data_single(benchmark):
    """Benchmark FloPy's head data extraction for single time step."""
    hds = HeadFile(FREYBERG_HDS)
    times = hds.get_times()
    mid_time = times[len(times) // 2]
    benchmark(lambda: hds.get_data(totim=mid_time))

def test_headfile_get_alldata(benchmark, function_tmpdir):
    """Benchmark reading entire head file."""
    hds = create_and_open_headfile(function_tmpdir)
    benchmark(hds.get_alldata)

def test_headfile_get_ts(benchmark, function_tmpdir):
    """Benchmark time series extraction."""
    hds = create_and_open_headfile(function_tmpdir)
    benchmark(lambda: hds.get_ts((0, 10, 10)))

@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_headfile_scaling(benchmark, function_tmpdir, size):
    """Benchmark HeadFile operations at different scales."""
    hds = create_headfile_with_size(function_tmpdir, size)
    benchmark(hds.get_alldata)
```

**CellBudgetFile Operations**:

Note: BudgetFile benchmarks use pre-existing files from examples/data directory to test FloPy's file parsing performance only, not MODFLOW runtime.

```python
# autotest/benchmarks/benchmark_utils_budget.py

from pathlib import Path
from flopy.utils import CellBudgetFile

FREYBERG_CBC = Path("examples/data/freyberg_multilayer_transient/freyberg.cbc")

@pytest.mark.skipif(not FREYBERG_CBC.exists(), reason="Example data not available")
def test_budgetfile_init_freyberg(benchmark):
    """Benchmark FloPy's CellBudgetFile initialization."""
    benchmark(lambda: CellBudgetFile(FREYBERG_CBC))

def test_budgetfile_get_data(benchmark, function_tmpdir):
    """Benchmark budget data extraction."""
    cbc = create_and_open_budgetfile(function_tmpdir)
    benchmark(lambda: cbc.get_data(text="FLOW RIGHT FACE"))

def test_budgetfile_list_records(benchmark, function_tmpdir):
    """Benchmark record listing."""
    cbc = create_and_open_budgetfile(function_tmpdir)
    benchmark(cbc.list_records)
```

**MODPATH Utilities**:

```python
# autotest/benchmarks/benchmark_utils_modpath.py

def test_pathlinefile_load(benchmark, function_tmpdir):
    """Benchmark PathlineFile loading."""
    pth_file = create_pathlinefile(function_tmpdir)
    benchmark(lambda: PathlineFile(pth_file))

def test_endpointfile_load(benchmark, function_tmpdir):
    """Benchmark EndpointFile loading."""
    ept_file = create_endpointfile(function_tmpdir)
    benchmark(lambda: EndpointFile(ept_file))

def test_pathline_to_dataframe(benchmark, function_tmpdir):
    """Benchmark pathline conversion to DataFrame."""
    pth = create_and_open_pathlinefile(function_tmpdir)
    benchmark(lambda: pth.get_destination_pathline_data(range(100)))
```

#### 2.3 Grid Operations

```python
# autotest/benchmarks/benchmark_grids.py

@pytest.mark.parametrize("grid_class", [
    StructuredGrid,
    VertexGrid,
    UnstructuredGrid,
])
def test_grid_init(benchmark, grid_class):
    """Benchmark grid initialization."""
    params = get_grid_params(grid_class)
    benchmark(lambda: grid_class(**params))

def test_grid_intersect_structured(benchmark):
    """Benchmark structured grid intersection."""
    grid = create_test_structured_grid()
    line = create_test_linestring()
    benchmark(lambda: grid.intersect(line))

def test_grid_get_lrc_large(benchmark):
    """Benchmark get_lrc for large models."""
    grid = create_large_structured_grid()
    nodes = range(0, grid.nnodes, 100)  # Sample every 100th node
    benchmark(lambda: [grid.get_lrc(node) for node in nodes])

def test_grid_get_node_large(benchmark):
    """Benchmark get_node for large models."""
    grid = create_large_structured_grid()
    lrc_tuples = [(0, i, j) for i in range(0, grid.nrow, 10)
                              for j in range(0, grid.ncol, 10)]
    benchmark(lambda: [grid.get_node(lrc) for lrc in lrc_tuples])
```

#### 2.4 Export Operations

```python
# autotest/benchmarks/benchmark_export.py

def test_export_shapefile_small(benchmark, function_tmpdir):
    """Benchmark shapefile export - small model."""
    model = create_small_test_model(function_tmpdir)
    output_path = function_tmpdir / "export.shp"
    benchmark(lambda: model.export(output_path))

def test_export_shapefile_large(benchmark, function_tmpdir):
    """Benchmark shapefile export - large model."""
    model = create_large_test_model(function_tmpdir)
    output_path = function_tmpdir / "export.shp"
    benchmark(lambda: model.export(output_path))

@pytest.mark.skipif(not has_pkg("geopandas"), reason="requires geopandas")
def test_export_geodataframe(benchmark, function_tmpdir):
    """Benchmark GeoDataFrame export (issue #2671)."""
    model = create_test_model(function_tmpdir)
    benchmark(lambda: model.to_gdf())

@pytest.mark.skipif(not has_pkg("netCDF4"), reason="requires netCDF4")
def test_export_netcdf(benchmark, function_tmpdir):
    """Benchmark NetCDF export."""
    model = create_test_model(function_tmpdir)
    output_path = function_tmpdir / "export.nc"
    benchmark(lambda: model.export(output_path, fmt="netcdf"))

@pytest.mark.skipif(not has_pkg("vtk"), reason="requires vtk")
def test_export_vtk(benchmark, function_tmpdir):
    """Benchmark VTK export."""
    model = create_test_model(function_tmpdir)
    output_path = function_tmpdir / "export.vtk"
    benchmark(lambda: model.export(output_path, fmt="vtk"))
```

#### 2.5 Array and Data Structure Benchmarks

```python
# autotest/benchmarks/benchmark_arrays.py

def test_util2d_create_large(benchmark):
    """Benchmark Util2d creation with large arrays."""
    shape = (100, 100)
    data = np.random.random(shape)
    benchmark(lambda: Util2d(None, shape, data))

def test_util2d_external_io(benchmark, function_tmpdir):
    """Benchmark Util2d external file I/O."""
    u2d = create_util2d_with_external(function_tmpdir)
    benchmark(u2d.get_file_entry)

def test_util3d_create_large(benchmark):
    """Benchmark Util3d creation with large arrays."""
    shape = (10, 100, 100)
    data = np.random.random(shape)
    benchmark(lambda: Util3d(None, shape, data))
```

#### 2.6 Pandas Integration Benchmarks

**Critical for validating ongoing refactor efforts:**

```python
# autotest/benchmarks/benchmark_pandas_io.py

def test_pandas_array_read(benchmark, function_tmpdir):
    """Benchmark pandas-based array reading."""
    # Compare pandas vs traditional approaches
    file_path = create_test_array_file(function_tmpdir)
    benchmark(lambda: read_array_pandas(file_path))

def test_pandas_list_read(benchmark, function_tmpdir):
    """Benchmark pandas-based list reading."""
    file_path = create_test_list_file(function_tmpdir)
    benchmark(lambda: read_list_pandas(file_path))

def test_pandas_array_write(benchmark, function_tmpdir):
    """Benchmark pandas-based array writing."""
    data = create_test_array_data()
    file_path = function_tmpdir / "test.dat"
    benchmark(lambda: write_array_pandas(data, file_path))

def test_mflist_pandas_performance(benchmark, function_tmpdir):
    """Benchmark MFList with pandas backend."""
    stress_period_data = create_large_stress_period_data()
    benchmark(lambda: MFList(stress_period_data))

def test_recarray_to_dataframe(benchmark):
    """Benchmark recarray to DataFrame conversion."""
    rec = create_large_recarray()
    benchmark(lambda: pd.DataFrame(rec))
```

### 3. Integration with modflow-devtools Models API

**Already Available**: The `modflow-devtools` package provides a models API with 442 models including:
- 242 MF6 test models (`mf6/test/*`)
- MF6 examples (`mf6/example/*`)
- MF6 large models (`mf6/large/*`)
- MODFLOW-2005 models (`mf2005/*`)

**Implementation**:

```python
# autotest/benchmarks/benchmark_models_api.py

from modflow_devtools.models import DEFAULT_REGISTRY
from flopy.mf6 import MFSimulation

# Select diverse models for benchmarking
BENCHMARK_MODELS = [
    "mf6/test/test001a_Tharmonic",
    "mf6/test/test006_gwf3",           # Multi-model
    "mf6/test/test006_gwf3_disv",      # DISV grid
    "mf6/test/test021_twri",           # Classic problem
    "mf6/test/test045_lake1ss_table",  # LAK package
]

@pytest.mark.parametrize("model_name", BENCHMARK_MODELS)
def test_mf6_load_from_registry(benchmark, function_tmpdir, model_name):
    """Benchmark FloPy loading models from devtools registry."""
    # Copy model to temp directory (setup, not benchmarked)
    DEFAULT_REGISTRY.copy_to(function_tmpdir, model_name)

    # Benchmark FloPy loading the model
    benchmark(lambda: MFSimulation.load(simulation_ws=function_tmpdir))
```

**Benefits**:
- 442 models available immediately (no waiting for issue #1872)
- Reproducible benchmarks across development environments
- Tests FloPy loading against diverse, real-world model inputs
- Community-standard test cases from MODFLOW 6 test suite
- On-demand download via Pooch (models cached locally)

### 4. Benchmark Organization

#### Proposed Directory Structure

```
autotest/
├── benchmarks/                    # NEW: Dedicated benchmark directory
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures, model builders
│   ├── test_io_mf6.py            # MF6 I/O benchmarks
│   ├── test_io_legacy.py         # Legacy MODFLOW variants
│   ├── test_utils_heads.py       # HeadFile operations (uses example data)
│   ├── test_utils_budget.py      # CellBudgetFile operations (uses example data)
│   ├── test_grids.py             # Grid operations
│   ├── test_export.py            # Export operations
│   ├── test_arrays.py            # Util2d/Util3d benchmarks
│   ├── test_pandas_io.py         # Pandas refactor validation
│   └── test_models_api.py        # Models API integration (future)
├── test_*.py                      # Existing test files
└── conftest.py                    # Global test configuration
```

#### Benchmark Markers

Define custom markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "benchmark: performance benchmarks",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

Usage:
```python
@pytest.mark.benchmark
def test_mf6_sim_load(benchmark, function_tmpdir):
    ...
```

### 5. CI/CD Strategy

#### Tiered Approach

**PR-Level (Fast Feedback)**:
```yaml
# .github/workflows/commit.yml - ADD TO EXISTING WORKFLOW
- name: Run fast benchmarks
  run: |
    pytest autotest/benchmarks \
      -m "benchmark and not slow" \
      --benchmark-only \
      --benchmark-disable-gc \
      --benchmark-warmup=on
```

**Daily Full Suite**:
```yaml
# .github/workflows/benchmark.yml - EXISTING, ENHANCED
- name: Run all benchmarks
  run: |
    pytest autotest/benchmarks \
      --benchmark-only \
      --benchmark-autosave \
      --codspeed
```

**Branch Comparisons**:
```yaml
# NEW: .github/workflows/benchmark-compare.yml
- name: Compare with develop branch
  run: |
    # Checkout develop
    git fetch origin develop
    git checkout develop
    pytest autotest/benchmarks --benchmark-only --benchmark-autosave

    # Checkout feature branch
    git checkout ${{ github.head_ref }}
    pytest autotest/benchmarks --benchmark-only --benchmark-compare
```

#### Codspeed Integration

**Benefits**:
- Automatic regression detection on PRs
- Performance trend visualization
- Historical comparison
- No manual artifact management

**Setup**:
1. Register FloPy repository at [codspeed.io](https://codspeed.io)
2. Add `CODSPEED_TOKEN` to repository secrets
3. Update workflow:
   ```yaml
   - uses: CodSpeedHQ/action@v3
     with:
       token: ${{ secrets.CODSPEED_TOKEN }}
       run: pytest autotest/benchmarks --codspeed
   ```

### 6. Performance Regression Tracking

#### Key Metrics to Monitor

1. **Pandas I/O Refactor Impact** (Primary Goal)
   - Array reading: Traditional vs pandas-based
   - List reading: Traditional vs pandas-based
   - Array writing: Traditional vs pandas-based
   - Expected: 10-50% improvement in most cases

2. **Model I/O by Size Category**
   - Small models (< 10k cells): Target < 100ms load
   - Medium models (10k-100k cells): Target < 1s load
   - Large models (> 100k cells): Monitor for regressions

3. **Package-Level Performance**
   - Identify expensive packages (large arrays: DIS, NPF, IC)
   - Track improvements over time

4. **Memory Usage**
   - Enable memory profiling for large model operations
   - Track memory efficiency of refactored code

#### Regression Thresholds

Configure pytest-benchmark comparison thresholds:

```python
# autotest/benchmarks/conftest.py

@pytest.fixture(scope="session")
def benchmark_config():
    return {
        "warmup": True,
        "warmup_iterations": 5,
        "max_time": 1.0,
        "min_rounds": 5,
        "timer": time.perf_counter,
        "disable_gc": True,
        "compare": {
            "func": "mean",
            "group": "fullname",
            "threshold": 1.05,  # 5% tolerance
        },
    }
```

**Alert Criteria**:
- > 5% slowdown: Warning (review required)
- > 10% slowdown: Failure (block merge)
- > 20% improvement: Document and celebrate!

### 7. Documentation

#### Developer Documentation Updates

Add comprehensive benchmarking section to `DEVELOPER.md`:

````markdown
#### Writing Benchmarks

Benchmarks follow standard pytest conventions with the `benchmark` fixture:

```python
# autotest/benchmarks/benchmark_example.py

def test_my_operation(benchmark, function_tmpdir):
    """Clear description of what is being benchmarked and why."""

    # Setup (not timed)
    model = create_test_model(function_tmpdir)

    # Benchmark the operation
    result = benchmark(model.write_input)

    # Optional assertions (not timed)
    assert result is not None
```

**Best Practices**:
- Use descriptive names: `test_mf6_large_model_load`, not `test_load1`
- Include docstrings explaining rationale
- Use fixtures for setup/teardown (not timed)
- Focus on one operation per benchmark
- Use parametrize for testing variations

**Running Benchmarks Locally**:

```bash
# Run all benchmarks
pytest autotest/benchmarks --benchmark-only

# Run specific benchmark file
pytest autotest/benchmarks/benchmark_io_mf6.py --benchmark-only

# Run with specific markers
pytest -m "benchmark and not slow" --benchmark-only

# Compare against saved baseline
pytest autotest/benchmarks --benchmark-only --benchmark-compare

# Save results
pytest autotest/benchmarks --benchmark-only --benchmark-autosave

# View statistics
pytest autotest/benchmarks --benchmark-only --benchmark-columns=mean,stddev,min,max
```

**Interpreting Results**:

Codspeed provides automated analysis, but for local runs:
- **Mean**: Primary metric (average execution time)
- **StdDev**: Consistency (lower is better)
- **Min**: Best-case performance
- **Iterations**: Number of runs (more = higher confidence)

**When to Add Benchmarks**:

1. Implementing performance-critical features
2. Refactoring I/O operations (e.g., pandas migration)
3. Optimizing existing code paths
4. Adding new model types or utilities
5. When performance is a key requirement
````

#### Template for New Benchmarks

Provide a template in `autotest/benchmarks/TEMPLATE.py`:

```python
"""
Benchmark template for FloPy operations.

Copy this template when creating new benchmark files.
"""
import pytest


# Fixtures for test data creation (setup not timed)
@pytest.fixture
def test_model(function_tmpdir):
    """Create a test model for benchmarking."""
    # Create and return model
    pass


# Basic benchmark
def test_operation_basic(benchmark, test_model):
    """
    Benchmark [operation description].

    This benchmark measures [what is being measured] to [why it matters].
    Expected baseline: [X]ms on [reference hardware].
    """
    result = benchmark(test_model.some_operation)
    assert result is not None


# Parametrized benchmark
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_operation_scaling(benchmark, function_tmpdir, size):
    """
    Benchmark [operation] at different scales.

    Measures how [operation] scales with [dimension].
    """
    model = create_model_with_size(function_tmpdir, size)
    benchmark(model.some_operation)


# Slow benchmark (excluded from PR checks)
@pytest.mark.slow
@pytest.mark.benchmark
def test_operation_large_dataset(benchmark, function_tmpdir):
    """
    Benchmark [operation] with realistic large dataset.

    Only run in daily benchmark suite due to runtime.
    """
    large_model = create_large_realistic_model(function_tmpdir)
    benchmark(large_model.some_operation)
```

### 8. Implementation Roadmap

#### Phase 1: Foundation (Weeks 1-2)

**Goals**: Set up infrastructure, reorganize existing benchmarks

- [ ] Create `autotest/benchmarks/` directory structure
- [ ] Add `pytest-codspeed` to dependencies
- [ ] Set up Codspeed integration (register, add token)
- [ ] Migrate existing 3 benchmarks from `test_modflow.py`
- [ ] Create shared fixtures in `benchmarks/conftest.py`
- [ ] Add benchmark markers to `pyproject.toml`
- [ ] Update `.github/workflows/benchmark.yml` for Codspeed
- [ ] Document new structure in `DEVELOPER.md`

**Deliverables**:
- Working Codspeed integration
- Reorganized benchmarks with clear structure
- Updated documentation

#### Phase 2: Core Coverage (Weeks 3-4)

**Goals**: Add essential MF6 and utility benchmarks

- [ ] Implement `test_io_mf6.py` (10-15 benchmarks)
  - Sim init (small, medium, large)
  - Sim write/load
  - Package-level operations
  - Multi-model simulations
- [ ] Implement `test_utils_heads.py` (8-10 benchmarks)
  - HeadFile init, get_data, get_alldata, get_ts
  - Scaling tests (small/medium/large)
- [ ] Implement `test_utils_budget.py` (5-8 benchmarks)
  - CellBudgetFile operations
- [ ] Establish baseline measurements for regression tracking

**Deliverables**:
- 25-35 new benchmarks
- Baseline performance data
- Initial regression thresholds set

#### Phase 3: Extended Coverage (Weeks 5-6)

**Goals**: Legacy models, grids, exports

- [ ] Implement `test_io_legacy.py` (10-12 benchmarks)
  - MODFLOW-NWT, MFUSG, SEAWAT, MT3DMS
  - Structured vs unstructured
  - Steady vs transient
- [ ] Implement `test_grids.py` (8-10 benchmarks)
  - Grid initialization
  - Intersection operations
  - get_lrc/get_node conversions
- [ ] Implement `test_export.py` (8-10 benchmarks)
  - Shapefile, GeoDataFrame, NetCDF, VTK

**Deliverables**:
- 25-30 additional benchmarks
- Comprehensive coverage of major FloPy operations
- Performance characterization across all model types

#### Phase 4: Pandas Validation & Polish (Weeks 7-8)

**Goals**: Validate refactor, finalize infrastructure

- [ ] Implement `test_pandas_io.py` (15-20 benchmarks)
  - Head-to-head pandas vs traditional
  - Array read/write
  - List operations
  - MFList performance
  - Recarray conversions
- [ ] Implement `test_arrays.py` (5-8 benchmarks)
  - Util2d/Util3d operations
- [ ] Add PR-level fast benchmark checks
- [ ] Create branch comparison workflow
- [ ] Generate performance improvement report for pandas refactor
- [ ] Polish documentation with examples and best practices
- [ ] Create benchmark template

**Deliverables**:
- Quantified pandas refactor performance gains
- Complete benchmark suite (80-120 total benchmarks)
- Full CI/CD integration
- Comprehensive documentation

#### Phase 5: Models API Integration (Available Now!)

**Goals**: Leverage modflow-devtools models registry

**Status**: ✅ Available - modflow-devtools already provides 442 models

- [ ] Implement `test_models_api.py` with representative sample (~10-15 models)
- [ ] Parametrize benchmarks across diverse model types
  - Multi-model simulations
  - Different grid types (DIS, DISV, DISU)
  - Various packages (LAK, SFR, UZF, MAW, etc.)
  - Transport models (GWT, GWE)
- [ ] Establish performance baselines for standard test suite
- [ ] Document model selection rationale

**Deliverables**:
- 10-15 benchmarks using modflow-devtools registry
- Coverage of diverse model complexity
- Community-standard performance baselines
- Validation of FloPy loading across official test suite

### 9. Success Criteria

#### Quantitative Metrics

1. **Coverage**: 80-100 benchmarks across all major FloPy operations
2. **CI Runtime**:
   - PR-level fast benchmarks: < 5 minutes
   - Daily full suite: < 30 minutes
3. **Pandas Refactor**: Demonstrate 10-50% improvement in I/O operations
4. **Regression Detection**: 100% of PRs receive automated performance feedback
5. **Historical Tracking**: 6+ months of continuous performance data

#### Qualitative Goals

1. **Developer Awareness**: Performance is a first-class consideration in PRs
2. **Confidence**: No unintended performance regressions in releases
3. **Documentation**: Clear guidelines for writing and interpreting benchmarks
4. **Community**: Performance data available for external analysis and comparison

### 10. Maintenance and Evolution

#### Ongoing Responsibilities

1. **Regular Review**: Quarterly review of benchmark relevance and thresholds
2. **Baseline Updates**: Reset baselines after intentional performance changes
3. **New Features**: All performance-critical features include benchmarks
4. **Cleanup**: Remove obsolete benchmarks when code is removed
5. **Reporting**: Annual performance report summarizing trends and improvements

#### Future Enhancements

1. **Memory Profiling**: Integrate memory usage tracking
2. **Parallel Benchmarks**: Test parallel performance (if applicable)
3. **Real-World Scenarios**: Benchmark complete workflows (load → modify → run → postprocess)
4. **Hardware Diversity**: Track performance across different CPU/memory configurations
5. **Comparison Reports**: Generate before/after reports for major refactors

## References

- [Issue #1989: Expand benchmarking](https://github.com/modflowpy/flopy/issues/1989)
- [Issue #1872: Models API](https://github.com/modflowpy/flopy/issues/1872)
- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/)
- [Codspeed documentation](https://docs.codspeed.io/)
- [FloPy DEVELOPER.md](../DEVELOPER.md)

## Appendix A: Example Benchmark Output

### pytest-benchmark Console Output

```
---------------------------- benchmark: 3 tests ----------------------------
Name (time in ms)                  Min       Max      Mean    StdDev    Rounds
---------------------------------------------------------------------------
test_model_init_time            12.34     15.67     13.21      0.89        50
test_model_write_time           45.23     52.11     47.89      2.34        20
test_model_load_time            78.90     89.12     82.45      3.12        15
---------------------------------------------------------------------------
```

### Codspeed PR Comment Example

```markdown
## ⚡ CodSpeed Performance Report

Performance changes detected in this PR:

| Benchmark | Status | Base | PR | Change |
|-----------|--------|------|----|---------|
| test_mf6_sim_load | 🔴 Slower | 145ms | 167ms | +15.2% |
| test_pandas_array_read | 🟢 Faster | 234ms | 187ms | -20.1% |
| test_headfile_get_data | ⚪ Unchanged | 56ms | 57ms | +1.8% |

[View full results on CodSpeed →](https://app.codspeed.io/...)
```

## Appendix B: Glossary

- **Benchmark**: Repeatable performance test measuring execution time
- **Baseline**: Reference performance measurement for comparison
- **Regression**: Unintended performance degradation
- **Round**: Single execution of benchmarked code
- **Warmup**: Initial executions discarded to account for JIT/caching effects
- **Fixture**: pytest test setup/teardown function (not timed)
- **Parametrize**: Run same benchmark with multiple input variations

---

**Document Version**: 1.0
**Authors**: FloPy Development Team
**License**: CC0 1.0 Universal
