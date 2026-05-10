from sqlmodel import Session, SQLModel, col, select

from db.database import get_engine


def seed_records(records: list[SQLModel]) -> int:
    """Insert records not already present, keyed on .id. Returns inserted count."""
    if not records:
        return 0

    model = type(records[0])
    incoming_ids = [r.id for r in records]  # type: ignore[attr-defined]
    with Session(get_engine()) as session:
        existing_ids = set(
            session.exec(
                select(col(model.id)).where(  # type: ignore[attr-defined]
                    col(model.id).in_(incoming_ids)  # type: ignore[attr-defined]
                )
            ).all()
        )
        new = [r for r in records if r.id not in existing_ids]  # type: ignore[attr-defined]
        session.add_all(new)
        session.commit()

    return len(new)
