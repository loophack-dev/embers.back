def main() -> None:
    """Run the API server (`uv run embers`)."""
    import uvicorn

    uvicorn.run("embers.main:create_app", factory=True, host="0.0.0.0", port=3523, log_config=None)
