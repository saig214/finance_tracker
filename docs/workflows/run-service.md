---
description: Start the web service
---

# Running the Finance Web Service

## Quick Start

To start the web interface:

```bash
python -m finance.cli web
```

Or if the package is installed in your PATH:

```bash
finance web
```

The service will start on **http://localhost:8000** by default.

## Options

- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 8000)
- `--reload`: Enable auto-reload (default: true)

## Example

```bash
# Run on a different port
finance web --port 8080

# Run on all interfaces
finance web --host 0.0.0.0
```

## Accessing the Dashboard

Once running, open your browser to:
- http://localhost:8000 (or the port you specified)

## Stopping the Service

Press `Ctrl+C` in the terminal to stop the server.
