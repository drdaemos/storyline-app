from src.services.dice_resolver import DiceResolver


class TestDiceResolver:
    def test_roll_d20_bounds(self) -> None:
        resolver = DiceResolver(seed=123)

        rolls = [resolver.roll_d20() for _ in range(200)]

        assert all(1 <= roll <= 20 for roll in rolls)

    def test_resolve_check_success_and_failure(self) -> None:
        resolver = DiceResolver(seed=1)

        success_result = resolver.resolve_check(
            character="Ren",
            skill="persuasion",
            skill_value=10,
            dc=12,
        )
        failure_result = resolver.resolve_check(
            character="Ren",
            skill="persuasion",
            skill_value=0,
            dc=25,
        )

        assert success_result.success is True
        assert success_result.total == success_result.roll + 10
        assert "vs DC 12" in success_result.detail

        assert failure_result.success is False
        assert failure_result.total == failure_result.roll
        assert "vs DC 25" in failure_result.detail

    def test_resolve_contested_check(self) -> None:
        resolver = DiceResolver(seed=7)

        result = resolver.resolve_contested(
            character="Ren",
            skill="intimidation",
            skill_value=3,
            opponent="Mara",
            opponent_skill="composure",
            opponent_skill_value=2,
        )

        assert result.contested is True
        assert result.character == "Ren"
        assert result.opponent == "Mara"
        assert result.opponent_total is not None
        assert isinstance(result.success, bool)
        assert "vs d20(" in result.detail
