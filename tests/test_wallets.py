from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Family, FamilyMember, MemberRole, User, WalletType
from app.services.permissions import PermissionDenied
from app.services.wallets import accessible_wallets, create_wallet


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


def test_admin_creates_wallet_and_sees_its_balance(session: Session) -> None:
    owner = User(telegram_user_id=1, display_name="Budi")
    session.add(owner)
    session.flush()
    family = Family(name="Keluarga Budi", created_by_user_id=owner.id)
    session.add(family)
    session.flush()
    session.add(FamilyMember(family_id=family.id, user_id=owner.id, role=MemberRole.OWNER))
    session.commit()

    with session.begin():
        wallet = create_wallet(session, family.id, owner.id, "Cash Budi", WalletType.CASH, 125_000)

    assert accessible_wallets(session, family.id, owner.id) == [(wallet, 125_000)]


def test_member_cannot_create_wallet(session: Session) -> None:
    owner = User(telegram_user_id=1, display_name="Budi")
    member = User(telegram_user_id=2, display_name="Andi")
    session.add_all((owner, member))
    session.flush()
    family = Family(name="Keluarga Budi", created_by_user_id=owner.id)
    session.add(family)
    session.flush()
    session.add_all(
        (
            FamilyMember(family_id=family.id, user_id=owner.id, role=MemberRole.OWNER),
            FamilyMember(family_id=family.id, user_id=member.id, role=MemberRole.MEMBER),
        )
    )
    session.commit()

    with pytest.raises(PermissionDenied):
        with session.begin():
            create_wallet(session, family.id, member.id, "Cash Andi", WalletType.CASH, 0)
