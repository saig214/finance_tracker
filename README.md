# 💰 Personal Finance Tracking System

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](#testing)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg)](#testing)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

*A comprehensive, open-source, local-first finance data platform that unifies your digital financial life.*

**⭐ Star this repo to show your support!**

---

## 📖 Overview

This project is a powerful, locally-hosted personal finance tracker designed to retain complete control over your financial data. It consolidates transactions from scattered sources—bank accounts, credit cards, and shared expense groups (Splitwise)—into a single, queryable database.

Unlike commercial tools that require you to upload your data to the cloud, this system runs 100% on your machine, ensuring maximum privacy while delivering professional-grade features like automated categorization, recurring transaction detection, and rich interactive dashboards.

## ✨ Key Features

### 🔌 Multi-Source Data Ingestion
- **Interactive Import Wizard**: Easily import data via a CLI wizard (`finance import`).
- **Credit Card Parsers**: Native support for password-protected PDF statements (HDFC, ICICI).
- **Universal CSV Support**: Configurable CSV parsers for any bank account.
- **Splitwise Integration**: Import full JSON backups to track shared expenses and debts.

### 🧠 Intelligent Processing
- **Merchant Normalization**: Automatically cleans messy bank descriptions (e.g., "UPI-SWIGGY-12345" → "Swiggy").
- **Smart Categorization**: Rule-based engine that learns from your history to tag transactions.
- **Deduplication**: Tree-based matching (date + amount + type + fuzzy description) ensures you never import the same transaction twice, even across format upgrades.
- **Audit Trail**: Every modification is logged in a `transformation_history` table for full data lineage.

### 📊 Rich Visualization & Reporting
- **Interactive Timeline**: Zoomable balance history chart to visualize net worth over time.
- **Spending Breakdowns**: Monthly and category-wise pie/bar charts.
- **Advanced Filtering**: Slice and dice data by merchant, category, account, or date range.

### 🤖 AI-Ready Architecture
- **Agent Discoverability**: Built-in CLI commands (`list-parsers --json`) allow AI agents to programmatically discover capabilities.
- **Structured Data**: Clean, normalized schema designed for easy SQL querying by LLMs.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- SQLite3

### Installation

1. **Clone and Install**
   ```bash
   git clone https://github.com/saig214/finance_tracker.git
   cd finance_tracker
   bash setup.sh && source .venv/bin/activate
   ```

2. **Configure Environment**
   Create a `.env` file to store secrets (optional but recommended):
   ```bash
   # .env
   DATABASE_URL=sqlite:///data/db/finance.db
   HDFC_PDF_PASSWORD=your_password
   ICICI_PDF_PASSWORD=your_password
   ```

3. **Initialize Database**
   ```bash
   finance init-db
   ```
   *This creates the database in `data/db/finance.db`.*

---

## 🌐 Running the Web Interface

Start the dashboard with a single command:
```bash
finance web
```

Then open your browser to: **http://localhost:8000**

*The service runs with auto-reload enabled by default, so code changes will be reflected immediately.*

---

## 📥 Importing Data

The system features a centralized **Import Wizard** that handles all data sources.

### Interactive Mode (Recommended)
Simply run:
```bash
finance import
```
Follow the on-screen prompts to:
1. Select the file to import.
2. Choose the source (Bank, Credit Card, Splitwise).
3. Provide any necessary credentials.

### Command Line Mode (For Scripts/Agents)
You can also run specific import commands directly:

```bash
# Import a Splitwise JSON backup
finance import-splitwise data/imports/splitwise.json

# Import a Bank CSV
finance import-bank-csv data/imports/statement.csv --profile generic_drcr

# Import a folder of HDFC PDFs
finance import-hdfc-batch data/imports/hdfc_stmts/ --password <pass>
```

---

## 📂 Project Structure

The project is organized to separate code, configuration, and data:

```
📦 finance
 ┣ 📂 data/                   # 🔒 ALL user data lives here (git-ignored)
 ┃ ┣ 📂 db/                   # SQLite databases
 ┃ ┗ 📂 imports/              # Raw statements and files
 ┣ 📂 src/finance/
 ┃ ┣ 📂 core/                 # Database models & configuration
 ┃ ┣ 📂 ingestion/            # Data parsers & registry
 ┃ ┃ ┗ 📂 parsers/            # 🔌 Plugin modules for each bank
 ┃ ┣ 📂 processing/           # Normalization & Categorization logic
 ┃ ┗ 📂 web/                  # FastAPI Dashboard
 ┗ 📄 README.md
```

---

## 🗺️ Roadmap

- [x] **Core Architecture**: Database schema, modular parsers.
- [x] **Data Ingestion**: Support for major Indian banks and Splitwise.
- [x] **Web UI**: Basic dashboards and transaction management.
- [x] **Splitwise Reconciliation**: Match shared expenses against bank transactions with effective amount tracking.
- [ ] **Budgeting**: Set monthly limits per category.
- [ ] **Investment Tracking**: Support for mutual funds and stock folios.

---

## 🧪 Testing

This project maintains high code quality through comprehensive testing.

### Run Tests

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov=src/finance --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Test Coverage

- **Overall coverage**: 85%+
- **Critical paths** (parsers, deduplication, categorization): 95%+
- **All new features require tests** before merging

See [docs/TESTING.md](docs/TESTING.md) for comprehensive testing guide.

---

## 🤝 Contributing

**We welcome contributions from the community!** Whether you're fixing bugs, adding features, improving documentation, or adding support for new banks, your contributions make this project better for everyone.

### Ways to Contribute

- **Add Bank Parsers**: Expand support for more financial institutions
- **Fix Bugs**: Help us squash issues
- **Improve Documentation**: Make it easier for others to use
- **Suggest Features**: Share your ideas
- **Review Code**: Help review pull requests

### Getting Started

1. **Read the [Contributing Guide](CONTRIBUTING.md)** - Complete guide to contributing
2. **Check [Good First Issues](https://github.com/saig214/finance_tracker/labels/good-first-issue)** - Perfect for newcomers
3. **Join Discussions** - Connect with other contributors
4. **Review [Development Guide](docs/DEVELOPMENT.md)** - Set up your dev environment

### Quick Contribution Guide

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/finance_tracker.git
cd finance_tracker

# 2. Create a branch
git checkout -b feature/my-awesome-feature

# 3. Make your changes and test
ruff check src/ tests/ --fix
ruff format src/ tests/
pytest

# 4. Commit and push
git commit -m "Add awesome feature"
git push origin feature/my-awesome-feature

# 5. Create a Pull Request on GitHub
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines, code standards, and the pull request process.

---

## 👥 Community

### Get Help

- **📖 Documentation**: Check our [comprehensive docs](docs/)
- **❓ Questions**: Open a [GitHub Discussion](https://github.com/saig214/finance_tracker/discussions)
- **🐛 Bug Reports**: [Open an issue](https://github.com/saig214/finance_tracker/issues/new)
- **💡 Feature Requests**: [Share your ideas](https://github.com/saig214/finance_tracker/issues/new)

### Resources

- **[User Guide](docs/USER_GUIDE.md)** - How to use the system
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Testing Guide](docs/TESTING.md)** - How to write and run tests
- **[Development Guide](docs/DEVELOPMENT.md)** - Set up your dev environment
- **[Architecture](docs/ARCHITECTURE.md)** - System design and structure
- **[Adding a Parser](docs/ADDING_A_PARSER.md)** - Add support for new banks

### Stay Updated

- **Watch** this repository for updates
- **Star** to show your support
- **Follow** the project for announcements

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### What This Means

You are free to:
- ✅ Use this software for personal or commercial purposes
- ✅ Modify the source code
- ✅ Distribute original or modified versions
- ✅ Use privately without sharing changes

Under the following conditions:
- 📝 Include the original license and copyright notice
- ⚠️ The software is provided "as is" without warranty

**TL;DR**: This is free, open-source software. Use it however you want, but please give credit.

---

## 🙏 Acknowledgments

This project is built with the help of:

- **Contributors**: Thank you to all who have contributed code, documentation, and ideas
- **Open Source Community**: Built on the shoulders of giants (SQLAlchemy, FastAPI, pytest, and more)
- **Users**: Your feedback and bug reports make this project better

### Built With

- [Python](https://www.python.org/) - Programming language
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [pytest](https://pytest.org/) - Testing framework
- [pikepdf](https://pikepdf.readthedocs.io/) - PDF processing
- [Click](https://click.palletsprojects.com/) - CLI framework

---

## 📊 Project Stats

- **Language**: Python 3.11+
- **License**: MIT
- **Status**: Active development
- **Tests**: 85%+ coverage
- **Supported Banks**: HDFC (CC + Bank PDF + CSV), ICICI (CC)

---

## ⚡ Quick Links

- [Installation](#-getting-started)
- [Usage Guide](docs/USER_GUIDE.md)
- [Add a New Bank Parser](docs/ADDING_A_PARSER.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Report a Bug](https://github.com/saig214/finance_tracker/issues/new)

---

## 🌟 Show Your Support

If this project helps you manage your finances better, please consider:

- ⭐ **Starring this repository**
- 🐛 **Reporting bugs** you encounter
- 💡 **Suggesting features** you'd like to see
- 🤝 **Contributing** code or documentation
- 📢 **Sharing** with others who might find it useful

**Every star and contribution motivates us to keep improving!**

---

**Made with ❤️ by the open-source community**