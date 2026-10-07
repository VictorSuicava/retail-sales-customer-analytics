"""Fingerprints for validation evidence; changed inputs invalidate prior checks."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analysis_fingerprint():
    paths = [ROOT/'scripts/pipeline.py', ROOT/'scripts/build_powerbi.py', ROOT/'sql/schema.sql',
             ROOT/'sql/analytics.sql', ROOT/'powerbi/measures.dax',
             ROOT/'powerbi/validation_queries.dax', ROOT/'powerbi/Retail.SemanticModel/model.bim']
    paths += sorted((ROOT/'data/processed').glob('*.csv'))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def report_fingerprint():
    return {p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted((ROOT/'powerbi/Retail.Report').rglob('*'))
            if p.is_file() and '.pbi' not in p.parts}
