# KC Tracker — Test Suite

## Structure
```
tests/
├── conftest.py                  # pytest path setup
├── test_balance_validator.py    # Balance math, amount cleaning
├── test_column_mapper.py        # Header mapping, DR/CR splitting
├── test_merchant_extractor.py   # UPI/NEFT merchant name cleaning
└── test_garbage_filter.py       # Row filtering, header/blacklist detection
```

## Run Tests

Install pytest first (one time):
```bash
pip install pytest
```

Run all tests:
```bash
pytest tests/ -v
```

Run a specific file:
```bash
pytest tests/test_balance_validator.py -v
```

Run a specific test:
```bash
pytest tests/test_balance_validator.py::TestCleanAmount::test_with_rupee_symbol -v
```

## Coverage (optional)
```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```
