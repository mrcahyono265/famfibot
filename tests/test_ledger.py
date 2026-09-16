from datetime import date
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Family, FamilyMember, MemberRole, TransactionType, User, Wallet, WalletType
from app.services.transactions import (
    RecordTransaction,
    TransactionRuleError,
    record_transaction,
    void_transaction,
    wallet_balance,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


def seed_workspace(session: Session):
    user = User(telegram_user_id=1, display_name="Budi")
    session.add(user)
    session.flush()
    family = Family(name="Keluarga Budi", created_by_user_id=user.id)
    session.add(family)
    session.flush()
    session.add(FamilyMember(family_id=family.id, user_id=user.id, role=MemberRole.OWNER))
    cash = Wallet(
        family_id=family.id,
        owner_user_id=user.id,
        name="Cash Budi",
        wallet_type=WalletType.CASH,
        initial_balance=100_000,
    )
    bank = Wallet(
        family_id=family.id,
        owner_user_id=user.id,
        name="BCA Budi",
        wallet_type=WalletType.BANK,
        initial_balance=0,
    )
    session.add_all((cash, bank))
    session.commit()
    return user, family, cash, bank


def test_income_expense_transfer_and_void_reconstruct_balance(session: Session) -> None:
    user, family, cash, bank = seed_workspace(session)

    with session.begin():
        expense = record_transaction(
            session,
            RecordTransaction(
                family_id=family.id,
                actor_user_id=user.id,
                transaction_type=TransactionType.EXPENSE,
                amount=25_000,
                description="Makan",
                transaction_date=date(2026, 9, 16),
                source_wallet_id=cash.id,
            ),
        )
        record_transaction(
            session,
            RecordTransaction(
                family_id=family.id,
                actor_user_id=user.id,
                transaction_type=TransactionType.INCOME,
                amount=50_000,
                description="Gaji",
                transaction_date=date(2026, 9, 16),
                destination_wallet_id=bank.id,
            ),
        )
        record_transaction(
            session,
            RecordTransaction(
                family_id=family.id,
                actor_user_id=user.id,
                transaction_type=TransactionType.TRANSFER,
                amount=40_000,
                description="Tarik tunai",
                transaction_date=date(2026, 9, 16),
                source_wallet_id=bank.id,
                destination_wallet_id=cash.id,
            ),
        )

    assert wallet_balance(session, family.id, cash.id) == 115_000
    assert wallet_balance(session, family.id, bank.id) == 10_000
    assert wallet_balance(session, family.id, cash.id) + wallet_balance(session, family.id, bank.id) == 125_000

    session.rollback()
    with session.begin():
        void_transaction(session, family.id, user.id, expense.id)

    assert wallet_balance(session, family.id, cash.id) == 140_000
    assert wallet_balance(session, family.id, bank.id) == 10_000


def test_transaction_cannot_use_wallet_from_another_workspace(session: Session) -> None:
    user, family, cash, _ = seed_workspace(session)
    other_user = User(telegram_user_id=2, display_name="Siti")
    session.add(other_user)
    session.flush()
    other_family = Family(name="Keluarga Siti", created_by_user_id=other_user.id)
    session.add(other_family)
    session.flush()
    session.add(FamilyMember(family_id=other_family.id, user_id=other_user.id, role=MemberRole.OWNER))
    other_wallet = Wallet(
        family_id=other_family.id,
        owner_user_id=other_user.id,
        name="Cash Siti",
        wallet_type=WalletType.CASH,
        initial_balance=0,
    )
    session.add(other_wallet)
    session.commit()

    with pytest.raises(TransactionRuleError):
        with session.begin():
            record_transaction(
                session,
                RecordTransaction(
                    family_id=family.id,
                    actor_user_id=user.id,
                    transaction_type=TransactionType.TRANSFER,
                    amount=10_000,
                    description="Tidak boleh lintas tenant",
                    transaction_date=date(2026, 9, 16),
                    source_wallet_id=cash.id,
                    destination_wallet_id=other_wallet.id,
                ),
            )
