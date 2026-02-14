# Contributing Guide

Thank you for your interest in contributing to the Personal Finance Tracking System! We welcome contributions of all kinds, from bug reports to new features, documentation improvements, and new bank parsers.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Pull Request Process](#pull-request-process)
- [Development Workflow](#development-workflow)
- [Adding a New Parser](#adding-a-new-parser)
- [Code Review Guidelines](#code-review-guidelines)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation Guidelines](#documentation-guidelines)
- [Community Guidelines](#community-guidelines)
- [Getting Help](#getting-help)

---

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow. By participating, you are expected to uphold this code.

**Our Pledge**: We are committed to providing a welcoming and inclusive environment for everyone, regardless of experience level, gender identity, sexual orientation, disability, personal appearance, body size, race, ethnicity, age, religion, or nationality.

**Expected Behavior**:
- Be respectful and considerate in your communication
- Welcome newcomers and help them get started
- Accept constructive criticism gracefully
- Focus on what is best for the community and project
- Show empathy towards other community members

**Unacceptable Behavior**:
- Harassment, trolling, or discriminatory language
- Publishing others' private information without permission
- Personal attacks or insults
- Other conduct which could reasonably be considered inappropriate

**Enforcement**: Project maintainers have the right to remove, edit, or reject comments, commits, code, issues, and other contributions that do not align with this Code of Conduct.

---

## How Can I Contribute?

### Ways to Contribute

1. **Report Bugs**: Help us identify issues and edge cases
2. **Suggest Features**: Share ideas for improvements
3. **Write Code**: Fix bugs, add features, or improve performance
4. **Improve Documentation**: Fix typos, add examples, or write guides
5. **Add Bank Parsers**: Expand support for more financial institutions
6. **Review Pull Requests**: Help review and test others' contributions
7. **Answer Questions**: Help other users in issues and discussions

### First-Time Contributors

Looking for a good first issue? Check for issues labeled:
- `good-first-issue`: Perfect for newcomers
- `help-wanted`: We'd love community help on these
- `documentation`: Improve our docs
- `parser`: Add support for a new bank

---

## Reporting Bugs

Good bug reports help us fix issues quickly and improve the project for everyone.

### Before Submitting a Bug Report

1. **Check existing issues**: Your bug might already be reported
2. **Update to latest version**: The bug might already be fixed
3. **Check documentation**: Ensure it's not a usage issue
4. **Collect information**: Gather logs, error messages, and reproduction steps

### How to Submit a Bug Report

Create an issue on GitHub with the following information:

**Bug Report Template**:

```markdown
## Bug Description
A clear and concise description of what the bug is.

## Steps to Reproduce
1. Run command '...'
2. Import file '...'
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Error Messages
```
Paste full error message here
```

## Environment
- OS: [e.g., Windows 11, Ubuntu 22.04, macOS 14]
- Python version: [e.g., 3.11.5]
- Finance version: [e.g., 0.1.0]
- Installation method: [e.g., pip install -e .]

## Additional Context
- Are you using a virtual environment?
- Any modifications to the code?
- Sample data (remove sensitive information!)

## Possible Solution (optional)
If you have ideas on how to fix this.
```

### Security Vulnerabilities

**Do not report security vulnerabilities through public GitHub issues.**

Instead, open a private security advisory on GitHub or email the maintainers with:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

---

## Suggesting Features

We love to hear your ideas for improving the project!

### Before Suggesting a Feature

1. **Check existing issues**: Your idea might already be proposed
2. **Check the roadmap**: It might already be planned
3. **Consider the scope**: Does it fit the project's goals?

### How to Suggest a Feature

Create an issue on GitHub with the following information:

**Feature Request Template**:

```markdown
## Feature Description
A clear and concise description of the feature.

## Problem Statement
What problem does this solve? Who would benefit?

## Proposed Solution
How should this feature work? Include examples.

## Example Usage
```bash
# Show how the feature would be used
finance new-command --example
```

## Alternatives Considered
What other approaches did you consider?

## Additional Context
- Related features in other projects
- Screenshots or mockups
- Links to relevant documentation
```

---

## Pull Request Process

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/finance_tracker.git
cd finance_tracker
git remote add upstream https://github.com/saig214/finance_tracker.git
```

### 2. Create a Branch

Use descriptive branch names following this convention:

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions or fixes

```bash
# Create and checkout a new branch
git checkout -b feature/add-axis-bank-parser
```

### 3. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 4. Test Your Changes

```bash
# Run linter
ruff check src/ tests/ --fix
ruff format src/ tests/

# Run tests
pytest

# Check coverage
pytest --cov=src/finance --cov-report=term-missing

# Test your changes manually
finance import --help
```

### 5. Commit Your Changes

Write clear, descriptive commit messages:

**Good commit message format**:
```
Add Axis Bank CSV parser

- Implements BaseParser interface for Axis Bank statements
- Supports both debit/credit and single amount column formats
- Handles date format DD/MM/YYYY and DD-MM-YYYY
- Includes comprehensive test coverage
- Updates parser registry and documentation

Closes #123
```

**Commit message guidelines**:
- First line: Brief summary (50 chars or less)
- Use imperative mood: "Add feature" not "Added feature"
- Reference issue numbers: "Closes #123" or "Fixes #456"
- Explain **why**, not just **what**

```bash
# Stage your changes
git add src/finance/ingestion/parsers/axis_bank.py
git add tests/test_axis_bank.py
git add docs/ADDING_A_PARSER.md

# Commit with a descriptive message
git commit -m "Add Axis Bank CSV parser

- Implements BaseParser interface
- Supports debit/credit columns
- Includes test coverage

Closes #123"
```

### 6. Push to Your Fork

```bash
git push origin feature/add-axis-bank-parser
```

### 7. Create Pull Request

Go to GitHub and create a pull request from your branch.

**Pull Request Template**:

```markdown
## Description
Brief description of the changes.

## Related Issue
Closes #123

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring

## Changes Made
- Added Axis Bank CSV parser
- Implemented date parsing for DD/MM/YYYY format
- Added 15 test cases covering edge cases
- Updated documentation

## Testing
- [ ] All existing tests pass
- [ ] New tests added and passing
- [ ] Manually tested with real data
- [ ] Coverage maintained above 80%

## Screenshots (if applicable)
Include screenshots for UI changes.

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added for new functionality
- [ ] All tests passing locally

## Additional Notes
Any additional information for reviewers.
```

### 8. Respond to Review Feedback

- Be responsive to reviewer comments
- Make requested changes promptly
- Ask questions if feedback is unclear
- Thank reviewers for their time

---

## Development Workflow

### Setup Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Initialize database
finance init

# Verify installation
finance --version
pytest --version
```

### Daily Development

```bash
# Update your local main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/my-feature

# Make changes and test frequently
pytest
ruff check src/ tests/ --fix

# Commit when tests pass
git commit -m "Description of changes"

# Push when ready
git push origin feature/my-feature
```

### Keep Your Fork Updated

```bash
# Fetch upstream changes
git fetch upstream

# Merge upstream main into your local main
git checkout main
git merge upstream/main

# Update your feature branch
git checkout feature/my-feature
git rebase main
```

---

## Adding a New Parser

Adding support for a new bank is one of the most valuable contributions! Follow this detailed guide to create a parser.

### 1. Create the Parser Class

Create a new file in `src/finance/ingestion/parsers/` (e.g., `my_bank.py`):

```python
"""Parser for My Bank statements."""

from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import List
import re

from finance.ingestion.base import BaseParser, ParseResult, RawTransaction
from finance.ingestion.registry import ParserRegistry


@ParserRegistry.register("my_bank")
class MyBankParser(BaseParser):
    """Parse My Bank CSV statements."""

    description = "My Bank Account Statement"
    supported_formats = ["csv"]
    required_args = []  # Add ["password"] if PDFs are encrypted

    @staticmethod
    def can_parse_filename(file_path: Path) -> bool:
        """Check if filename matches My Bank pattern."""
        # Implement bank-specific filename detection
        pattern = r"my_bank_statement_\d{6}\.csv"
        return bool(re.match(pattern, file_path.name.lower()))

    def can_parse(self, file_path: Path) -> bool:
        """Check if file can be parsed by this parser."""
        if not self.can_parse_filename(file_path):
            return False

        # Additional validation (check content, headers, etc.)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                return 'Date,Description,Amount' in first_line
        except Exception:
            return False

    def parse(self, file_path: Path) -> ParseResult:
        """Parse the bank statement file."""
        transactions = []
        errors = []
        warnings = []

        try:
            # Read and parse file
            import csv
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        tx = self._parse_row(row)
                        if tx:
                            transactions.append(tx)
                    except Exception as e:
                        errors.append(f"Row parsing error: {str(e)}")

        except Exception as e:
            errors.append(f"File parsing error: {str(e)}")

        return ParseResult(
            transactions=transactions,
            errors=errors,
            warnings=warnings,
            source_type='my_bank_account',
            file_hash=self._compute_file_hash(file_path),
            file_size=file_path.stat().st_size,
            metadata={'parser': 'my_bank', 'version': '1.0'}
        )

    def _parse_row(self, row: dict) -> RawTransaction:
        """Parse a single CSV row into a transaction."""
        date_str = row['Date']
        description = row['Description']
        amount_str = row['Amount']

        # Parse date
        tx_date = datetime.strptime(date_str, '%d/%m/%Y')

        # Parse amount
        amount = Decimal(amount_str.replace(',', ''))

        return RawTransaction(
            transaction_date=tx_date,
            amount=abs(amount),
            currency='INR',
            original_description=description,
            metadata={'raw_amount': amount_str}
        )
```

### 2. Register and Export the Parser

Add your parser to `src/finance/ingestion/parsers/__init__.py`:

```python
from .my_bank import MyBankParser

__all__ = [
    # ... other parsers ...
    'MyBankParser',
]
```

### 3. Write Comprehensive Tests

Create `tests/test_my_bank.py`:

```python
"""Unit tests for My Bank parser."""

import pytest
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from finance.ingestion.parsers.my_bank import MyBankParser


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample My Bank CSV file."""
    csv_file = tmp_path / "my_bank_statement_202601.csv"
    csv_content = """Date,Description,Amount
01/01/2026,Opening Balance,10000.00
02/01/2026,ATM Withdrawal,-500.00
03/01/2026,Salary Deposit,5000.00
"""
    csv_file.write_text(csv_content)
    return csv_file


def test_can_parse_valid_filename():
    """Test that valid filenames are recognized."""
    assert MyBankParser.can_parse_filename(Path("my_bank_statement_202601.csv"))
    assert not MyBankParser.can_parse_filename(Path("other_bank.csv"))


def test_parse_valid_file(sample_csv):
    """Test parsing a valid CSV file."""
    parser = MyBankParser()
    result = parser.parse(sample_csv)

    assert result.success
    assert len(result.transactions) == 3
    assert result.transactions[0].amount == Decimal('10000.00')


def test_handles_invalid_date(tmp_path):
    """Test handling of invalid dates."""
    csv_file = tmp_path / "my_bank_statement_202601.csv"
    csv_file.write_text("Date,Description,Amount\n99/99/2026,Invalid,-100.00")

    parser = MyBankParser()
    result = parser.parse(csv_file)

    assert len(result.errors) > 0
```

### 4. Update Documentation

Add your parser to the documentation:

- Update `docs/ADDING_A_PARSER.md` with bank-specific details
- Add example usage to `README.md`
- Include sample commands in `docs/USER_GUIDE.md`

### 5. Verify Everything Works

```bash
# List parsers (should include your new parser)
finance list-parsers

# Get parser details
finance parser-info my_bank

# Run tests
pytest tests/test_my_bank.py -v

# Test with real data (use sample file)
finance import sample_statement.csv
```

---

## Code Review Guidelines

### For Contributors

**Before requesting review**:
- [ ] All tests pass locally
- [ ] Code is formatted with `ruff format`
- [ ] No linting errors (`ruff check`)
- [ ] Documentation updated
- [ ] Self-review completed

**During review**:
- Respond to feedback promptly
- Be open to suggestions
- Ask questions if unclear
- Update PR based on feedback

### For Reviewers

**What to review**:
- [ ] Code correctness and logic
- [ ] Test coverage and quality
- [ ] Performance implications
- [ ] Security considerations
- [ ] Documentation accuracy
- [ ] Code style and readability
- [ ] Breaking changes

**How to review**:
- Be constructive and specific
- Explain the "why" behind suggestions
- Approve when ready, even if minor issues remain
- Use GitHub's suggestion feature for small fixes

**Review checklist**:
```markdown
- [ ] Code is clean and readable
- [ ] Logic is sound and efficient
- [ ] Tests are comprehensive
- [ ] Documentation is clear
- [ ] No security issues
- [ ] Follows project conventions
- [ ] Ready to merge
```

---

## Coding Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line length**: 100 characters (not 79)
- **Quotes**: Prefer double quotes for strings
- **Imports**: Sorted and grouped (handled by ruff)
- **Type hints**: Encouraged but not required

### Code Formatting

```bash
# Format code automatically
ruff format src/ tests/

# Check for issues
ruff check src/ tests/

# Auto-fix issues
ruff check src/ tests/ --fix
```

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `HDFCCreditCardParser`)
- **Functions**: `snake_case` (e.g., `parse_transaction`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Private methods**: `_leading_underscore` (e.g., `_parse_row`)

### Documentation Strings

```python
def parse_amount(amount_str: str) -> Decimal:
    """Parse amount string to Decimal.

    Args:
        amount_str: Amount as string, may include commas and currency symbols

    Returns:
        Parsed amount as Decimal

    Raises:
        ValueError: If amount string cannot be parsed

    Example:
        >>> parse_amount("1,234.56")
        Decimal('1234.56')
    """
    # Implementation
    pass
```

---

## Testing Requirements

### Test Coverage

- **Minimum**: 80% overall coverage
- **New code**: Must include tests
- **Bug fixes**: Must include regression test
- **Critical paths**: 95%+ coverage required

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/finance

# Run specific test
pytest tests/test_my_parser.py::test_specific_function

# Run and generate HTML report
pytest --cov=src/finance --cov-report=html
```

### Writing Good Tests

```python
def test_parser_handles_empty_file(tmp_path):
    """Test that parser gracefully handles empty files.

    This test verifies that:
    1. Empty files don't crash the parser
    2. Appropriate warnings/errors are returned
    3. Result indicates failure appropriately
    """
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    parser = MyBankParser()
    result = parser.parse(empty_file)

    assert not result.success
    assert len(result.errors) > 0 or len(result.warnings) > 0
```

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide.

---

## Documentation Guidelines

### Documentation Types

1. **Code comments**: Explain **why**, not **what**
2. **Docstrings**: API documentation for functions/classes
3. **README**: High-level overview and quick start
4. **Guides**: Step-by-step tutorials (in `docs/`)
5. **Reference**: Detailed technical documentation

### Writing Good Documentation

**Good**:
```python
def normalize_upi_description(desc: str) -> str:
    """Extract merchant name from UPI transaction description.

    UPI transactions have format: "UPI-MERCHANT-REF12345"
    This extracts just the merchant name.
    """
```

**Bad**:
```python
def normalize_upi_description(desc: str) -> str:
    """Normalizes description."""  # Too vague
```

### Documentation Updates

When making changes, update:
- [ ] Code docstrings
- [ ] README.md (if adding features)
- [ ] Relevant guides in `docs/`
- [ ] CHANGELOG.md (for version updates)

---

## Community Guidelines

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **Pull Requests**: Code contributions and review
- **Discussions**: General questions, ideas, help
- **Email**: Security issues (private)

### Response Times

We strive to:
- **Acknowledge** issues within 48 hours
- **Review** PRs within 5 business days
- **Merge** approved PRs within 2 days

Please be patient! This is a community project maintained by volunteers.

### Recognition

Contributors are recognized in:
- Git commit history
- CONTRIBUTORS.md file
- Release notes
- Documentation credits

Thank you for making this project better!

---

## Getting Help

### Documentation Resources

- **[README.md](README.md)**: Project overview
- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**: Usage instructions
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**: Common issues
- **[docs/TESTING.md](docs/TESTING.md)**: Testing guide
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**: Development setup
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System design

### Getting Help

1. **Check documentation**: Most questions are answered there
2. **Search issues**: Your question might already be answered
3. **Ask in Discussions**: For general questions
4. **Open an issue**: For specific problems
5. **Join community**: Connect with other contributors

### Contact Maintainers

- **General questions**: Open a GitHub Discussion
- **Bug reports**: Open a GitHub Issue
- **Security issues**: Open a [private security advisory](https://github.com/saig214/finance_tracker/security/advisories)
- **Other inquiries**: Open a [GitHub Discussion](https://github.com/saig214/finance_tracker/discussions)

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

**Thank you for contributing to the Personal Finance Tracking System!** Every contribution, no matter how small, helps make this project better for everyone.
