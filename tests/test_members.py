from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Family, FamilyMember, GroupMember, GroupType, MemberRole, MembershipStatus, User
from app.services.members import bind_group, request_group_membership, approve_member
from app.services.permissions import PermissionDenied


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session


def test_owner_binds_group_and_approves_join_request(session: Session) -> None:
    owner = User(telegram_user_id=1, display_name="Budi")
    sibling = User(telegram_user_id=2, display_name="Andi")
    session.add_all((owner, sibling))
    session.flush()
    family = Family(name="Keluarga Budi", created_by_user_id=owner.id)
    session.add(family)
    session.flush()
    session.add(FamilyMember(family_id=family.id, user_id=owner.id, role=MemberRole.OWNER))
    session.commit()

    with session.begin():
        group = bind_group(session, family.id, owner.id, -1001, "Parents", GroupType.PARENTS)
        assert request_group_membership(session, group, sibling)

    family_member = session.query(FamilyMember).filter_by(family_id=family.id, user_id=sibling.id).one()
    group_member = session.query(GroupMember).filter_by(group_id=group.id, user_id=sibling.id).one()
    assert family_member.status == MembershipStatus.PENDING
    assert group_member.status == MembershipStatus.PENDING
    session.commit()

    with session.begin():
        assert approve_member(session, family.id, owner.id, sibling)

    assert family_member.status == MembershipStatus.ACTIVE
    assert group_member.status == MembershipStatus.ACTIVE

    with session.begin():
        second_group = bind_group(session, family.id, owner.id, -1002, "General", GroupType.GENERAL)
        assert request_group_membership(session, second_group, sibling)
        assert approve_member(session, family.id, owner.id, sibling)

    assert session.query(GroupMember).filter_by(group_id=second_group.id, user_id=sibling.id).one().status == MembershipStatus.ACTIVE


def test_member_cannot_bind_group(session: Session) -> None:
    owner = User(telegram_user_id=1, display_name="Budi")
    member = User(telegram_user_id=2, display_name="Andi")
    session.add_all((owner, member))
    session.flush()
    family = Family(name="Keluarga Budi", created_by_user_id=owner.id)
    session.add(family)
    session.flush()
    session.add_all((
        FamilyMember(family_id=family.id, user_id=owner.id, role=MemberRole.OWNER),
        FamilyMember(family_id=family.id, user_id=member.id, role=MemberRole.MEMBER),
    ))
    session.commit()

    with pytest.raises(PermissionDenied):
        with session.begin():
            bind_group(session, family.id, member.id, -1001, "Parents", GroupType.PARENTS)
