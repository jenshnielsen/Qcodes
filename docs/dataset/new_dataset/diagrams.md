```mermaid
graph LR
AA[doNd] -- Creates --> A
AB[ManualCreate] -- Creates --> A
AC[Other?] -- Creates --> A
A[DataSetDefinition] -- dd.execute() --> D[Dataset]
A -- with dd.manual_measurement(): --> D[Dataset]
```

`DataSetDefinition` replaces current `DataSetDefinition` as well as `RunDescription` + `InterDeps` within the dataset.
The definition must be flexible enough to support both dataset on a grid and non-gridded dataset and be extendable to other data types as needed.
Need to discuss if the `DataSetDefinition` needs to embed logic for actions ...


```
with dd.manual_execute() as ds: <- create a dataset that is preallocated to the correct shape.
                                    If shape is not known allocate N points and grow *2 on each reallocation.
                                    Writes dataset metadata, guid etc
    ds.add_result({param: val}) <-- Add data to buffer. For each chunk of data of size n (configurable)
                                    data is flushed to disk. Could be zarr chunked dir or similar.
                                    Backend must be configurable. Flushing should happen on background thread


__exit__ <- Finalize dataset (set shapes, cleanup extra allocation, zip, convert to other format, sends signal, trigger entry point etc.
```
What should happen for interrupted measurements. Should remaining data be written as `NaN` or excluded





For reference the existing measurement context manager:

```mermaid
classDiagram
    direction LR

    class DataSaver {
        +default_callback: dict | None
        -_dataset: DataSetProtocol
        -_interdeps: InterDependencies_
        -_results: list
        -_registered_parameters: Sequence~ParameterBase~
        +write_period: float
        +parent_datasets: list~DataSetProtocol~
        +add_result(*result_tuples: ResType) None
        +flush_data_to_database(block: bool) None
        +export_data() None
        +run_id: int
        +points_written: int
        +dataset: DataSetProtocol
        -_validate_result_deps(results_dict) None
        -_validate_result_shapes(results_dict) None
        -_validate_result_types(results_dict) None
        -_unpack_arrayparameter(partial_result) dict
        -_unpack_multiparameter(partial_result) dict
        -_unpack_setpoints_from_parameter(...) dict
    }

    class Runner {
        +enteractions: Sequence~ActionType~
        +exitactions: Sequence~ActionType~
        +subscribers: Sequence~SubscriberType~
        +experiment: Experiment | None
        +station: Station | None
        +name: str
        +write_period: float
        +ds: DataSetProtocol
        +datasaver: DataSaver
        -_interdependencies: InterDependencies_
        -_shapes: Shapes | None
        -_dataset_class: DataSetType
        -_write_in_background: bool
        -_in_memory_cache: bool
        -_registered_parameters: Sequence~ParameterBase~
        +__enter__() DataSaver
        +__exit__(exception_type, exception_value, traceback) None
        -_calculate_write_period(write_in_background, write_period) float
    }

    class Measurement {
        +exitactions: list~ActionType~
        +enteractions: list~ActionType~
        +subscribers: list~SubscriberType~
        +experiment: Experiment | None
        +station: Station | None
        +name: str
        +write_period: float
        -_interdeps: InterDependencies_
        -_shapes: Shapes | None
        -_parent_datasets: list
        -_registered_parameters: set~ParameterBase~
        +parameters: dict
        +register_parameter(parameter, setpoints, basis, paramtype) Self
        +register_custom_parameter(name, label, unit, ...) Self
        +unregister_parameter(parameter) None
        +register_parent(parent, link_type, description) Self
        +add_before_run(func, args) Self
        +add_after_run(func, args) Self
        +add_subscriber(func, state) Self
        +set_shapes(shapes) None
        +run(write_in_background, in_memory_cache, ...) Runner
        -_self_register_parameter(parameter, setpoints, basis) Self
        -_register_parameter(name, label, unit, ...) Self
        -_register_arrayparameter(...) None
        -_register_multiparameter(...) None
        -_register_parameter_with_setpoints(...) None
        -_infer_paramtype(parameter, paramtype) str
    }

    Measurement --> Runner : run() creates
    Runner --> DataSaver : __enter__() creates
    DataSaver --> "1" DataSetProtocol : _dataset
```
