"""
Module to handle validating the consistency of data in the Parquet file and the
metadata in the MAML file. 

TODO #4: Extend this to validate the consistency of the DAML file too. 
"""

from dataclasses import dataclass
import polars as pl

from .status import Status, State
from .data_types import ClosedInterval, ANSI
from .helper_validator_methods import check_column_range, check_data_type
from .metadata_validator import ColumnMetaData, MamlMetaData


def _compare_column_type(column_name: str, data: pl.DataFrame, metadata_columns: dict[str, ColumnMetaData]) -> Status:
    """
    Compares the information for the given column name in both the data and the metadata. 
    """
    if check_data_type(data[column_name].dtype, metadata_columns[column_name].data_type):
      return Status(State.PASS)
    else:
      return Status(State.FAIL, f"Invalid datatype. MAML indicates the expected type is {metadata_columns[column_name].data_type} but the Parquet shows type actually is {data[column_name].dtype}")


def _compare_column_range(column_name: str, data: pl.DataFrame, metadata_columns: dict[str, ColumnMetaData]) -> Status:
    """
    Compares the information for the given column name in both the data and the metadata. 
    """
    is_valid = check_column_range(data, column_name, 
                               metadata_columns[column_name].qc.min, 
                               metadata_columns[column_name].qc.max, 
                               ClosedInterval.BOTH)
    
    if is_valid:
      return Status(State.PASS)
    else:
      return Status(State.FAIL, f"Invalid range. Data must be between the supplied minimum {metadata_columns[column_name].qc.min} and the supplied maximum {metadata_columns[column_name].qc.max}")
        

@dataclass
class DataMetadataValueReport:
    column_name: str
    column_in_both_files: Status 
    valid_column_datatypes: Status | None
    valid_column_ranges: Status | None

    def __post_init__(self) -> None:
        self.valid = all(
            [
                self.column_in_both_files.state == State.PASS,
                self.valid_column_datatypes and self.valid_column_datatypes.state == State.PASS,
                self.valid_column_ranges and self.valid_column_ranges.state == State.PASS,
            ]
        )

    def print_report(self, verbose=False) -> None:
        """
        Print a professional validation report with color-coded results.
        """
        # Helper function for status
        def status(given_status: Status) -> str:
            match given_status.state:
                case State.PASS:
                    return f"{ANSI.GREEN}✓ PASS{ANSI.RESET}"
                case State.FAIL:
                    return f"{ANSI.RED}✗ FAIL{ANSI.RESET}"
                case State.WARNING:
                    return f"{ANSI.YELLOW}⚠ WARNING"

        # Overall column status
        overall_color = ANSI.GREEN if self.valid else ANSI.RED
        overall_status = "VALID" if self.valid else "INVALID"
        print(f"\n{ANSI.BOLD}Column:{ANSI.RESET} {self.column_name} | {ANSI.BOLD}Overall Status:{ANSI.RESET} {overall_color}{overall_status}{ANSI.RESET}")

        if not self.valid or verbose:
          print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
          print(f"{'-' * 80}")
          
          column_in_both_files_info = f"\n     {ANSI.RED} → {self.column_in_both_files.message}.{ANSI.RESET}" if self.column_in_both_files.state == State.FAIL else ""
          if self.column_in_both_files.state == State.FAIL or verbose:
              print(
                  f"  Column present in both files:                 {status(self.column_in_both_files)}{column_in_both_files_info}"
              )


          if self.valid_column_datatypes:
            valid_column_datatypes_info = f"\n     {ANSI.RED} → {self.valid_column_datatypes.message}.{ANSI.RESET}" if self.valid_column_datatypes.state == State.FAIL else ""
            if self.valid_column_datatypes.state == State.FAIL or verbose:
                print(
                    f"  Valid column datatype:                        {status(self.valid_column_datatypes)} {valid_column_datatypes_info}"
                )

          if self.valid_column_ranges:
            valid_column_ranges_info = f"\n     {ANSI.RED} → {self.valid_column_ranges.message}.{ANSI.RESET}" if self.valid_column_ranges.state == State.FAIL else ""
            if self.valid_column_ranges.state == State.FAIL or verbose:
                print(
                    f"  Valid column range:                           {status(self.valid_column_ranges)} {valid_column_ranges_info}"
                )

          print(f"{'-' * 80}")


def validate_data_and_metadata(table_name: str, data: pl.DataFrame, metadata: MamlMetaData) -> list[DataMetadataValueReport]:
    """
    Validates the columns in the data and MAML files. Checks for: 
    1. Columns appearing in both the data and the MAML,
    2. Columns having the datatype as indicated by the MAML, and
    3. Columns having the range as indicated by the MAML 
    """
    metadata_columns = metadata.fields
    all_columns = set(data.columns) | set(metadata_columns.columns)

    column_reports: list[DataMetadataValueReport] = []

    for column_name in all_columns:
        in_both_files = Status(State.PASS)
        valid_range = None
        valid_datatype = None

        if column_name in data.columns and column_name in metadata_columns.columns:
          in_both_files = Status(State.PASS)
          if metadata_columns.columns[column_name].qc:
              valid_range = _compare_column_range(column_name, data, metadata_columns.columns)
          else:
              valid_range = Status(State.PASS)
          valid_datatype = _compare_column_type(column_name, data, metadata_columns.columns)

          column_reports.append(DataMetadataValueReport(column_name, in_both_files, valid_datatype, valid_range))
        elif column_name in data.columns and column_name not in metadata_columns.columns:
          in_both_files = Status(State.FAIL, f"{column_name} found in {table_name}.parquet but not in {table_name}.maml")
          column_reports.append(DataMetadataValueReport(column_name, in_both_files, valid_datatype, valid_range))
        elif column_name not in data.columns and column_name in metadata_columns.columns:
          in_both_files = Status(State.FAIL, f"{column_name} found in {table_name}.maml but not in {table_name}.parquet")
          column_reports.append(DataMetadataValueReport(column_name, in_both_files, valid_datatype, valid_range))

    return column_reports
