import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol
from src.domain.exceptions import GameNotFoundError, PlayerNotFoundError, InvalidGameActionError
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.enums import TransactionType, PropertyGroup, TileType
from src.domain.models.game import Game
from src.domain.models.player import Player
from src.domain.models.transaction import Transaction
from src.domain.rules.rule_registry import BoardRuleRegistry
from src.domain.rules.rule_hooks import RulesetEngine
from src.domain.themes.card_models import DeckType, CardEffectType, ThemeCardDefinition
from src.domain.themes.theme_registry import ThemeRegistry
from src.domain.themes.classic import CLASSIC_THEME
from src.application.dtos.action_dtos import DrawCardInputDTO, DrawCardOutputDTO


@dataclass
class CardExecutionContext:
    game: Game
    player: Player
    card: ThemeCardDefinition
    all_players: List[Player]
    property_repo: PropertyRepositoryProtocol
    player_repo: PlayerRepositoryProtocol
    game_repo: GameRepositoryProtocol
    tx_repo: TransactionRepositoryProtocol
    effective_roll: int = 7


@dataclass
class CardExecutionResult:
    amount_delta: int = 0
    old_position: int = 0
    new_position: int = 0
    passed_go: bool = False
    in_jail: bool = False
    landed_tile_action: Optional[str] = None
    landed_tile_details: Optional[Dict[str, Any]] = None
    tx_id: Optional[int] = None
    audit_description: str = ""


class CardEffectStrategy(Protocol):
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        ...


class CollectFromBankStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        amount = int(ctx.card.params.get("amount", 0))
        ctx.player.add_money(amount)
        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=amount,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} cobró ${amount} de la Banca. ({ctx.card.description})",
                source_player_id=None,
                target_player_id=ctx.player.id,
                tile_id=None,
            )
        )
        return CardExecutionResult(
            amount_delta=amount,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class PayToBankStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        amount = int(ctx.card.params.get("amount", 0))
        pay_amount = min(ctx.player.money, amount)
        ctx.player.deduct_money(pay_amount)
        ctx.player_repo.save(ctx.player)

        # Regla de pozo de Parada Libre (RulesetEngine)
        RulesetEngine.process_tax_or_fine(ctx.game, ctx.player, pay_amount)
        ctx.game_repo.save(ctx.game)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=pay_amount,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} pagó ${pay_amount} a la Banca. ({ctx.card.description})",
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )
        return CardExecutionResult(
            amount_delta=-pay_amount,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class CollectFromAllStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        amount_per_player = int(ctx.card.params.get("amount", 0))
        active_rivals = [p for p in ctx.all_players if p.id != ctx.player.id and not p.is_bankrupt]
        total_collected = 0

        for rival in active_rivals:
            pay = min(rival.money, amount_per_player)
            if pay > 0:
                rival.deduct_money(pay)
                ctx.player.add_money(pay)
                ctx.player_repo.save(rival)
                total_collected += pay

        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=total_collected,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} cobró ${total_collected} en total de los demás jugadores (${amount_per_player} c/u). ({ctx.card.description})",
                source_player_id=None,
                target_player_id=ctx.player.id,
                tile_id=None,
            )
        )
        return CardExecutionResult(
            amount_delta=total_collected,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class PayToAllStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        amount_per_player = int(ctx.card.params.get("amount", 0))
        active_rivals = [p for p in ctx.all_players if p.id != ctx.player.id and not p.is_bankrupt]
        total_paid = 0

        for rival in active_rivals:
            pay = min(ctx.player.money, amount_per_player)
            if pay > 0:
                ctx.player.deduct_money(pay)
                rival.add_money(pay)
                ctx.player_repo.save(rival)
                total_paid += pay

        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=total_paid,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} pagó ${total_paid} en total a los demás jugadores (${amount_per_player} c/u). ({ctx.card.description})",
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )
        return CardExecutionResult(
            amount_delta=-total_paid,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class MoveToPositionStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        old_pos = ctx.player.position
        target_pos = int(ctx.card.params.get("target_pos", 0))
        collect_go = bool(ctx.card.params.get("collect_go", True))

        passed_go = (target_pos < old_pos or target_pos == 0) and collect_go and (target_pos != old_pos or target_pos == 0)
        salary_paid = 0

        if passed_go:
            is_exact = (target_pos == 0)
            salary_paid = RulesetEngine.calculate_go_salary(ctx.game, ctx.player, is_exact_landing=is_exact)
            ctx.player.add_money(salary_paid)
            ctx.tx_repo.record(
                Transaction(
                    id=None,
                    game_id=ctx.game.id,
                    turn_number=ctx.game.current_turn,
                    transaction_type=TransactionType.PASS_GO,
                    amount=salary_paid,
                    description=f"🚩 {ctx.player.name} avanzó por carta a la casilla #{target_pos} pasando por Salida y cobró ${salary_paid}",
                    source_player_id=None,
                    target_player_id=ctx.player.id,
                    tile_id="GO",
                )
            )

        ctx.player.position = target_pos
        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=0,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} se trasladó a la casilla #{target_pos}. ({ctx.card.description})",
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )

        return CardExecutionResult(
            amount_delta=salary_paid,
            old_position=old_pos,
            new_position=target_pos,
            passed_go=passed_go,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class MoveRelativeStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        old_pos = ctx.player.position
        steps = int(ctx.card.params.get("steps", 0))
        collect_go = bool(ctx.card.params.get("collect_go", False))

        new_pos = (old_pos + steps) % 40
        passed_go = (steps > 0 and new_pos < old_pos and collect_go)
        salary_paid = 0

        if passed_go:
            salary_paid = RulesetEngine.calculate_go_salary(ctx.game, ctx.player, is_exact_landing=(new_pos == 0))
            ctx.player.add_money(salary_paid)

        ctx.player.position = new_pos
        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=0,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} se movió {steps} casillas (de #{old_pos} a #{new_pos}). ({ctx.card.description})",
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )

        return CardExecutionResult(
            amount_delta=salary_paid,
            old_position=old_pos,
            new_position=new_pos,
            passed_go=passed_go,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class MoveNearestTypeStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        old_pos = ctx.player.position
        target_type = str(ctx.card.params.get("tile_type", "RAILROAD")).upper()
        multiplier = int(ctx.card.params.get("rent_multiplier", 2))

        railroad_positions = [5, 15, 25, 35]
        utility_positions = [12, 28]
        candidates = railroad_positions if "RAILROAD" in target_type else utility_positions

        # Buscar la siguiente casilla en sentido horario
        dest_pos = None
        for p in candidates:
            if p > old_pos:
                dest_pos = p
                break
        if dest_pos is None:
            dest_pos = candidates[0]  # Vuelta al tablero

        passed_go = (dest_pos < old_pos)
        salary_paid = 0
        if passed_go:
            salary_paid = RulesetEngine.calculate_go_salary(ctx.game, ctx.player, is_exact_landing=False)
            ctx.player.add_money(salary_paid)
            ctx.tx_repo.record(
                Transaction(
                    id=None,
                    game_id=ctx.game.id,
                    turn_number=ctx.game.current_turn,
                    transaction_type=TransactionType.PASS_GO,
                    amount=salary_paid,
                    description=f"🚩 {ctx.player.name} cruzó la Salida rumbo a la estación/servicio #{dest_pos} y cobró ${salary_paid}",
                    source_player_id=None,
                    target_player_id=ctx.player.id,
                    tile_id="GO",
                )
            )

        ctx.player.position = dest_pos
        ctx.player_repo.save(ctx.player)

        # Evaluar la casilla de destino para renta especial o compra
        board = BoardRuleRegistry.get_board(ctx.game.variant)
        tile_strategy = next((s for s in board.values() if s.definition.position == dest_pos), None)
        tile_action = None
        tile_details = None
        net_rent_paid = 0

        if tile_strategy:
            t_def = tile_strategy.definition
            prop = ctx.property_repo.get_by_tile(ctx.game.id, t_def.tile_id)
            if not prop or prop.owner_id is None:
                tile_action = "BUY_PROPERTY"
                tile_details = {
                    "price": t_def.price,
                    "tile_id": t_def.tile_id,
                    "tile_name": t_def.name,
                    "can_afford": ctx.player.can_afford(t_def.price),
                }
            elif prop.owner_id == ctx.player.id:
                tile_action = "OWNED_BY_SELF"
                tile_details = {"tile_id": t_def.tile_id, "tile_name": t_def.name}
            else:
                # Dueño es rival
                if prop.is_mortgaged:
                    tile_action = "MORTGAGED_NO_RENT"
                    tile_details = {"tile_id": t_def.tile_id, "tile_name": t_def.name}
                else:
                    owner = ctx.player_repo.get_by_id(prop.owner_id)
                    all_props = ctx.property_repo.list_by_owner(ctx.game.id, prop.owner_id)
                    
                    if "UTILITY" in target_type:
                        # 10 veces el resultado de los dados
                        calculated_rent = multiplier * ctx.effective_roll
                    else:
                        # Doble de la renta debida
                        base_rent = tile_strategy.calculate_rent(prop, all_props, ctx.effective_roll)
                        calculated_rent = base_rent * multiplier

                    rent_to_pay = min(ctx.player.money, calculated_rent)
                    if rent_to_pay > 0:
                        ctx.player.deduct_money(rent_to_pay)
                        if owner:
                            owner.add_money(rent_to_pay)
                            ctx.player_repo.save(owner)
                        ctx.player_repo.save(ctx.player)
                        net_rent_paid = rent_to_pay

                    ctx.tx_repo.record(
                        Transaction(
                            id=None,
                            game_id=ctx.game.id,
                            turn_number=ctx.game.current_turn,
                            transaction_type=TransactionType.PAY_RENT,
                            amount=rent_to_pay,
                            description=f"🏠 {ctx.player.name} pagó ${rent_to_pay} de renta especial (x{multiplier}) a {owner.name if owner else 'rival'} en {t_def.name}",
                            source_player_id=ctx.player.id,
                            target_player_id=owner.id if owner else None,
                            tile_id=t_def.tile_id,
                        )
                    )
                    tile_action = "SPECIAL_RENT_PAID"
                    tile_details = {
                        "tile_id": t_def.tile_id,
                        "tile_name": t_def.name,
                        "rent_paid": rent_to_pay,
                        "multiplier": multiplier,
                        "owner_id": prop.owner_id,
                    }

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=0,
                description=f"🃏 [{ctx.card.title}] {ctx.player.name} avanzó a la casilla #{dest_pos} ({target_type}). ({ctx.card.description})",
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )

        return CardExecutionResult(
            amount_delta=salary_paid - net_rent_paid,
            old_position=old_pos,
            new_position=dest_pos,
            passed_go=passed_go,
            landed_tile_action=tile_action,
            landed_tile_details=tile_details,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class GoToJailStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        old_pos = ctx.player.position
        ctx.player.in_jail = True
        ctx.player.jail_turns = 0
        ctx.player.position = 10
        ctx.player_repo.save(ctx.player)

        # Regla oficial: pierde cualquier turno extra y el turno finaliza
        ctx.game.consecutive_doubles = 0
        ctx.game.has_rolled_dice = False
        ctx.game.advance_turn(len(ctx.all_players))
        ctx.game_repo.save(ctx.game)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=0,
                description=f"👮 [{ctx.card.title}] {ctx.player.name} fue enviado directamente a la Cárcel por carta. ({ctx.card.description})",
                source_player_id=None,
                target_player_id=ctx.player.id,
                tile_id="GO_TO_JAIL",
            )
        )

        return CardExecutionResult(
            amount_delta=0,
            old_position=old_pos,
            new_position=10,
            in_jail=True,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class GetOutOfJailCardStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        ctx.player.out_of_jail_cards += 1
        ctx.player_repo.save(ctx.player)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=0,
                description=f"🎟️ [{ctx.card.title}] {ctx.player.name} obtuvo la tarjeta 'Salga de la Cárcel Gratis'. Total en posesión: {ctx.player.out_of_jail_cards}.",
                source_player_id=None,
                target_player_id=ctx.player.id,
                tile_id=None,
            )
        )

        return CardExecutionResult(
            amount_delta=0,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class RepairsPerBuildingStrategy:
    def execute(self, ctx: CardExecutionContext) -> CardExecutionResult:
        house_cost = int(ctx.card.params.get("house_cost", 25))
        hotel_cost = int(ctx.card.params.get("hotel_cost", 100))

        owned_props = ctx.property_repo.list_by_owner(ctx.game.id, ctx.player.id)
        total_houses = sum(p.houses_count for p in owned_props)
        total_hotels = sum(p.hotels_count for p in owned_props)

        total_cost = (total_houses * house_cost) + (total_hotels * hotel_cost)
        pay_amount = min(ctx.player.money, total_cost)

        if pay_amount > 0:
            ctx.player.deduct_money(pay_amount)
            ctx.player_repo.save(ctx.player)

        # Regla de pozo de Parada Libre (RulesetEngine)
        RulesetEngine.process_tax_or_fine(ctx.game, ctx.player, pay_amount)
        ctx.game_repo.save(ctx.game)

        tx_type = TransactionType.CHANCE_CARD if ctx.card.deck == DeckType.CHANCE else TransactionType.COMMUNITY_CHEST_CARD
        tx = ctx.tx_repo.record(
            Transaction(
                id=None,
                game_id=ctx.game.id,
                turn_number=ctx.game.current_turn,
                transaction_type=tx_type,
                amount=pay_amount,
                description=(
                    f"🔨 [{ctx.card.title}] {ctx.player.name} pagó ${pay_amount} por reparaciones "
                    f"({total_houses} casas a ${house_cost}, {total_hotels} hoteles a ${hotel_cost}). ({ctx.card.description})"
                ),
                source_player_id=ctx.player.id,
                target_player_id=None,
                tile_id=None,
            )
        )

        return CardExecutionResult(
            amount_delta=-pay_amount,
            old_position=ctx.player.position,
            new_position=ctx.player.position,
            tx_id=tx.id,
            audit_description=tx.description,
        )


class CardEffectExecutor:
    """
    Despachador extensible de efectos mecánicos de cartas (Open/Closed Principle & Strategy).
    Evita bloques monolíticos de if/elif asociando cada CardEffectType a su estrategia dedicada.
    """
    _strategies: Dict[CardEffectType, Any] = {
        CardEffectType.COLLECT_FROM_BANK: CollectFromBankStrategy(),
        CardEffectType.PAY_TO_BANK: PayToBankStrategy(),
        CardEffectType.COLLECT_FROM_ALL: CollectFromAllStrategy(),
        CardEffectType.PAY_TO_ALL: PayToAllStrategy(),
        CardEffectType.MOVE_TO_POSITION: MoveToPositionStrategy(),
        CardEffectType.MOVE_RELATIVE: MoveRelativeStrategy(),
        CardEffectType.MOVE_NEAREST_TYPE: MoveNearestTypeStrategy(),
        CardEffectType.GO_TO_JAIL: GoToJailStrategy(),
        CardEffectType.GET_OUT_OF_JAIL_CARD: GetOutOfJailCardStrategy(),
        CardEffectType.REPAIRS_PER_BUILDING: RepairsPerBuildingStrategy(),
    }

    @classmethod
    def execute(cls, ctx: CardExecutionContext) -> CardExecutionResult:
        strategy = cls._strategies.get(ctx.card.effect_type)
        if not strategy:
            raise InvalidGameActionError(f"Efecto de carta no soportado: '{ctx.card.effect_type}'.")
        return strategy.execute(ctx)


class DrawCardUseCase:
    """
    Caso de uso desacoplado para robar y ejecutar cartas de Fortuna o Arca Comunal.
    Maneja el barajado inicial, la retención de cartas especiales y el reciclaje al fondo del mazo.
    """

    def __init__(
        self,
        game_repo: GameRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        property_repo: PropertyRepositoryProtocol,
        tx_repo: TransactionRepositoryProtocol,
    ):
        self._game_repo = game_repo
        self._player_repo = player_repo
        self._property_repo = property_repo
        self._tx_repo = tx_repo

    def execute(self, dto: DrawCardInputDTO, effective_roll: int = 7) -> DrawCardOutputDTO:
        # 1. Validar partida y jugador
        game = self._game_repo.get_by_id(dto.game_id)
        if not game:
            raise GameNotFoundError(f"Partida {dto.game_id} no encontrada.")

        player = self._player_repo.get_by_id(dto.player_id)
        if not player or player.game_id != game.id:
            raise PlayerNotFoundError(f"Jugador {dto.player_id} no válido para la partida.")

        all_players = self._player_repo.list_by_game(game.id)

        # 2. Determinar tipo de mazo y tema activo
        deck_str = dto.deck_type.upper()
        if "COMMUNITY" in deck_str or "ARCA" in deck_str:
            deck_type = DeckType.COMMUNITY_CHEST
        else:
            deck_type = DeckType.CHANCE

        theme = ThemeRegistry.get_theme(game.theme_id) or CLASSIC_THEME
        deck_name = theme.chance_deck_name if deck_type == DeckType.CHANCE else theme.community_chest_deck_name

        # 3. Barajar si el mazo de la partida está vacío
        current_order = game.get_deck_order(deck_type.value)
        if not current_order:
            all_theme_cards = theme.get_deck_cards(deck_type)
            card_ids = [c.card_id for c in all_theme_cards]
            random.shuffle(card_ids)
            current_order = card_ids
            game.set_deck_order(deck_type.value, current_order)

        # 4. Seleccionar carta
        target_card_id = dto.card_id
        if target_card_id:
            # Si se especificó una carta forzada, removerla del orden si existe
            if target_card_id in current_order:
                current_order.remove(target_card_id)
            selected_card_id = target_card_id
        else:
            selected_card_id = game.pop_next_card(deck_type.value)
            if not selected_card_id:
                # Fallback de seguridad
                all_theme_cards = theme.get_deck_cards(deck_type)
                selected_card_id = all_theme_cards[0].card_id

        card_def = theme.get_card(selected_card_id)
        if not card_def:
            raise InvalidGameActionError(f"Carta '{selected_card_id}' no encontrada en el tema '{theme.theme_id}'.")

        # 5. Ejecutar efecto de la carta
        ctx = CardExecutionContext(
            game=game,
            player=player,
            card=card_def,
            all_players=all_players,
            property_repo=self._property_repo,
            player_repo=self._player_repo,
            game_repo=self._game_repo,
            tx_repo=self._tx_repo,
            effective_roll=effective_roll,
        )
        res = CardEffectExecutor.execute(ctx)

        # 6. Regla oficial de retención y reciclaje:
        # Si es GET_OUT_OF_JAIL_CARD, la carta no regresa al mazo mientras el jugador la conserve.
        # De lo contrario, regresa inmediatamente al fondo del mazo.
        if card_def.effect_type != CardEffectType.GET_OUT_OF_JAIL_CARD:
            game.put_card_at_bottom(deck_type.value, card_def.card_id)

        self._game_repo.save(game)

        return DrawCardOutputDTO(
            game_id=game.id,
            player_id=player.id,
            player_name=player.name,
            deck_type=deck_type.value,
            deck_name=deck_name,
            card_id=card_def.card_id,
            title=card_def.title,
            description=card_def.description,
            effect_type=card_def.effect_type.value,
            amount_delta=res.amount_delta,
            old_position=res.old_position,
            new_position=res.new_position,
            passed_go=res.passed_go,
            in_jail=res.in_jail,
            out_of_jail_cards_count=player.out_of_jail_cards,
            transaction_id=res.tx_id,
            landed_tile_action=res.landed_tile_action,
            landed_tile_details=res.landed_tile_details,
            message=res.audit_description or card_def.description,
        )
