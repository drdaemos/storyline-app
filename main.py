from dotenv import load_dotenv

def run() -> None:
    """Load local configuration before Click resolves environment options."""
    load_dotenv()


if __name__ == "__main__":
    run()
