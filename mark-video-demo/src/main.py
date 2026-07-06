from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def main() -> None:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    print("Mark video demo project is ready.")
    print(f"Assets directory: {ASSETS_DIR}")
    print(f"Outputs directory: {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
