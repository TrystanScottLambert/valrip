import polars as pl

from .settings_config import protected_words
from .WAVES_config import MinMax, ColumnMetaData, WAVESDataTypes
from .ucd_validator import guess_ucd


def fields_from_lf(
    lazy_frame: pl.LazyFrame, web_search: bool = True
) -> list[ColumnMetaData] | None:
    """
    Automatically generating as much field metadata as possible.
    """
    schema = lazy_frame.collect_schema()
    column_names = schema.names()

    try:
        data_types = [
            WAVESDataTypes.polars_dtype_to_WAVES_data_type(dtype)
            for dtype in schema.dtypes()
        ]

        agg = (
            lazy_frame.select(
                *[pl.col(c).min().alias(f"{c}__min") for c in column_names],
                *[pl.col(c).max().alias(f"{c}__max") for c in column_names],
            )
            .collect()
            .row(0, named=True)
        )

        mins = [agg[f"{c}__min"] for c in column_names]
        maxs = [agg[f"{c}__max"] for c in column_names]

        qcs = [
            MinMax(min, max) if not isinstance(min, str) else None
            for min, max in zip(mins, maxs)
        ]

        ucds = [guess_ucd(name, web_search) for name in column_names]

        units = []
        for column_name in column_names:
            possible_unit = "--"
            for protected_word in protected_words:
                if len(protected_word.name.split("_")) > 1:
                    if protected_word.name in column_name:
                        if possible_unit == "--":
                            possible_unit = protected_word.unit[0]
                for word in column_name.split("_"):
                    if word == protected_word.name:
                        if possible_unit == "--":
                            possible_unit = protected_word.unit[0]
            units.append(possible_unit)

        field_data = []
        for name, data_type, ucd, qc, unit in zip(
            column_names, data_types, ucds, qcs, units
        ):
            field_data.append(ColumnMetaData(name, ucd, data_type, qc, unit=unit))
        return field_data
    except ValueError as e:
        print(e)
        return None
