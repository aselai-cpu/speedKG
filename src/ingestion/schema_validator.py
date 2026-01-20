"""
SPEED CSV Schema Validator

Validates CSV schema integrity before ingestion to catch issues early.

Checks:
- Expected field count (106 columns)
- Required fields presence
- No duplicate columns
- Valid data types in sample
- Event ID uniqueness
- Temporal field ranges
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validate CSV schema before ingestion."""

    # Required fields that must be present
    REQUIRED_FIELDS = [
        'eventid',
        'year', 'month', 'day',
        'EV_TYPE',
        'NEWS_SOURCE'
    ]

    # Expected total field count
    EXPECTED_FIELD_COUNT = 106

    # Fields that should be numeric
    NUMERIC_FIELDS = [
        'year', 'month', 'day',
        'EV_TYPE', 'PE_TYPE', 'ATK_TYPE', 'DSA_TYPE',
        'INI_TYPE', 'TAR_TYPE', 'VIC_TYPE',
        'N_KILLED_P', 'N_KILLED_A', 'N_INJURD',
        'arrests', 'DAY_SPAN'
    ]

    # Temporal bounds
    MIN_YEAR = 1900
    MAX_YEAR = 2100
    MIN_MONTH = 1
    MAX_MONTH = 12
    MIN_DAY = 1
    MAX_DAY = 31

    def validate(self, csv_path: Path, sample_size: int = 1000) -> Tuple[bool, List[str]]:
        """
        Validate CSV schema integrity.

        Args:
            csv_path: Path to CSV file
            sample_size: Number of rows to sample for validation

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        logger.info(f"Validating schema: {csv_path}")

        try:
            # Read header only (use latin1 encoding for older CSV files)
            df_header = pd.read_csv(csv_path, nrows=0, encoding='latin1')
            columns = df_header.columns.tolist()

            # Check 1: Field count
            if len(columns) != self.EXPECTED_FIELD_COUNT:
                errors.append(
                    f"Expected {self.EXPECTED_FIELD_COUNT} fields, found {len(columns)}"
                )
                logger.warning(f"Field count mismatch: expected {self.EXPECTED_FIELD_COUNT}, got {len(columns)}")

            # Check 2: Required fields
            missing_fields = [f for f in self.REQUIRED_FIELDS if f not in columns]
            if missing_fields:
                errors.append(f"Missing required fields: {', '.join(missing_fields)}")
                logger.error(f"Missing required fields: {missing_fields}")

            # Check 3: Duplicate columns
            duplicates = [col for col in columns if columns.count(col) > 1]
            if duplicates:
                errors.append(f"Duplicate columns: {', '.join(set(duplicates))}")
                logger.error(f"Duplicate columns found: {set(duplicates)}")

            # Read sample rows for data quality checks
            logger.info(f"Reading {sample_size} sample rows for validation")
            df_sample = pd.read_csv(
                csv_path,
                nrows=sample_size,
                low_memory=False,
                encoding='latin1'
            )

            # Check 4: Event ID uniqueness in sample
            if 'eventid' in df_sample.columns:
                if df_sample['eventid'].duplicated().any():
                    dup_count = df_sample['eventid'].duplicated().sum()
                    errors.append(f"Duplicate event IDs found in sample: {dup_count}")
                    logger.warning(f"Found {dup_count} duplicate event IDs in sample")

            # Check 5: Temporal field ranges
            if 'year' in df_sample.columns:
                invalid_years = df_sample[
                    (df_sample['year'] < self.MIN_YEAR) |
                    (df_sample['year'] > self.MAX_YEAR)
                ]
                if len(invalid_years) > 0:
                    errors.append(
                        f"Invalid year values detected: {len(invalid_years)} rows "
                        f"outside range {self.MIN_YEAR}-{self.MAX_YEAR}"
                    )
                    logger.warning(f"Invalid year values: {len(invalid_years)} rows")

            if 'month' in df_sample.columns:
                invalid_months = df_sample[
                    (df_sample['month'] < self.MIN_MONTH) |
                    (df_sample['month'] > self.MAX_MONTH)
                ]
                if len(invalid_months) > 0:
                    errors.append(
                        f"Invalid month values detected: {len(invalid_months)} rows"
                    )

            if 'day' in df_sample.columns:
                invalid_days = df_sample[
                    (df_sample['day'] < self.MIN_DAY) |
                    (df_sample['day'] > self.MAX_DAY)
                ]
                if len(invalid_days) > 0:
                    errors.append(
                        f"Invalid day values detected: {len(invalid_days)} rows"
                    )

            # Check 6: Event type values (should be 1, 2, 4, or 5)
            if 'EV_TYPE' in df_sample.columns:
                valid_types = {1, 2, 4, 5}
                invalid_types = df_sample[
                    ~df_sample['EV_TYPE'].isna() &
                    ~df_sample['EV_TYPE'].isin(valid_types)
                ]
                if len(invalid_types) > 0:
                    errors.append(
                        f"Invalid EV_TYPE values detected: {len(invalid_types)} rows "
                        f"(valid: {valid_types})"
                    )

            # Check 7: Data completeness
            completeness = self._check_completeness(df_sample)
            logger.info(f"Data completeness: {completeness['overall_complete']:.1%}")

            if completeness['overall_complete'] < 0.01:  # Less than 1% complete
                errors.append(
                    f"Very low data completeness: {completeness['overall_complete']:.1%}"
                )

            # Check 8: Critical fields have some data
            critical_fields = ['eventid', 'year', 'EV_TYPE']
            for field in critical_fields:
                if field in df_sample.columns:
                    missing_pct = df_sample[field].isna().sum() / len(df_sample)
                    if missing_pct > 0.5:  # More than 50% missing
                        errors.append(
                            f"Critical field '{field}' has {missing_pct:.1%} missing values"
                        )

            # Summary
            if errors:
                logger.error(f"Schema validation failed with {len(errors)} errors")
                return False, errors
            else:
                logger.info("Schema validation passed")
                return True, []

        except FileNotFoundError:
            errors.append(f"File not found: {csv_path}")
            logger.error(f"File not found: {csv_path}")
            return False, errors
        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
            logger.error(f"Validation exception: {e}", exc_info=True)
            return False, errors

    def _check_completeness(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check data completeness.

        Args:
            df: DataFrame to check

        Returns:
            Dictionary with completeness statistics
        """
        total_cells = df.shape[0] * df.shape[1]
        non_null_cells = df.count().sum()
        overall_complete = non_null_cells / total_cells if total_cells > 0 else 0

        # Field-level completeness
        field_completeness = {}
        for col in df.columns:
            completeness = df[col].count() / len(df) if len(df) > 0 else 0
            field_completeness[col] = completeness

        # Identify fields with very low completeness (< 10%)
        sparse_fields = [
            col for col, comp in field_completeness.items()
            if comp < 0.1
        ]

        return {
            "overall_complete": overall_complete,
            "total_cells": total_cells,
            "non_null_cells": int(non_null_cells),
            "sparse_fields_count": len(sparse_fields),
            "sparse_fields": sparse_fields[:10]  # First 10
        }

    def validate_and_report(self, csv_path: Path, sample_size: int = 1000) -> bool:
        """
        Validate and print detailed report.

        Args:
            csv_path: Path to CSV file
            sample_size: Number of rows to sample

        Returns:
            True if valid, False otherwise
        """
        is_valid, errors = self.validate(csv_path, sample_size)

        print("\n" + "=" * 60)
        print("SPEED CSV SCHEMA VALIDATION REPORT")
        print("=" * 60)
        print(f"File: {csv_path}")
        print(f"Sample size: {sample_size} rows")
        print()

        if is_valid:
            print("✅ VALIDATION PASSED")
            print()
            print("Schema is valid and ready for ingestion.")
        else:
            print("❌ VALIDATION FAILED")
            print()
            print(f"Found {len(errors)} error(s):")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")

        print("=" * 60)
        print()

        return is_valid


def main():
    """CLI for schema validation."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python schema_validator.py <csv_file> [sample_size]")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    sample_size = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    validator = SchemaValidator()
    is_valid = validator.validate_and_report(csv_path, sample_size)

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
