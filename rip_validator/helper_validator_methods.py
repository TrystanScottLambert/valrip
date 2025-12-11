import polars as pl

from .data_types import ANSI, ClosedInterval

def check_data_type(polars_dtype: pl.DataType, waves_type: str) -> bool:
    return str(polars_dtype).lower() == waves_type.lower()

def check_column_range(
    data_frame: pl.DataFrame,
    column_name: str,
    min: float,
    max: float,
    include: ClosedInterval,
) -> bool:
    """
    Determines if a given column name is between the min max values assuming [min, max].
    Interval closed or open can be handled with the ClosedInterval enum.
    """
    contained = data_frame.select(
        pl.col(column_name).is_between(min, max, closed=include.value).all()
    ).item()
    return contained

def print_header(heading):
      print(f"\n{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")
      print(f"{ANSI.BOLD}{heading}{ANSI.RESET}")
      print(f"{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")
