from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import MemberRole, Portfolio, Position, Team, User


def test_team_user_portfolio_position_can_be_persisted():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(name="Core Research")
        user = User(email="analyst@example.com", display_name="Analyst")
        portfolio = Portfolio(team=team, name="Main Book", base_currency="USD")
        position = Position(
            portfolio=portfolio,
            ticker="AAPL",
            quantity=10,
            average_cost=150,
            currency="USD",
        )
        session.add(team)
        session.add(user)
        session.add(portfolio)
        session.add(position)
        session.commit()

    with Session(engine) as session:
        stored = session.exec(select(Position).where(Position.ticker == "AAPL")).one()
        assert stored.quantity == 10
        assert stored.portfolio.name == "Main Book"


def test_member_role_values_are_stable():
    assert MemberRole.owner.value == "owner"
    assert MemberRole.analyst.value == "analyst"
    assert MemberRole.viewer.value == "viewer"
