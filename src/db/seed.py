from dotenv import load_dotenv

from db.database import init_db


def seed_all() -> None:
    load_dotenv()
    init_db()

    import src.db.seeds as _seeds

    for name in _seeds.__all__:
        module = getattr(_seeds, name)
        n = module.load()
        print(f"{name}: {n} inserted")


if __name__ == "__main__":
    seed_all()
