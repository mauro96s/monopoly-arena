from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from src.domain.interfaces.game_repository import GameRepositoryProtocol
from src.domain.interfaces.player_repository import PlayerRepositoryProtocol
from src.domain.interfaces.property_repository import PropertyRepositoryProtocol
from src.domain.interfaces.transaction_repository import TransactionRepositoryProtocol
from src.domain.models.enums import GameStatus, TransactionType
from src.domain.models.game import Game
from src.domain.models.transaction import Transaction
from src.domain.rules.rule_registry import BoardRuleRegistry


@dataclass
class QuickEndResult:
    triggered: bool
    winner_id: Optional[int] = None
    winner_name: Optional[str] = None
    winner_token: Optional[str] = None
    winner_net_worth: Optional[int] = None
    rankings: List[Dict[str, Any]] = field(default_factory=list)
    disqualified_player_ids: List[int] = field(default_factory=list)
    reason: str = ""
    transaction_id: Optional[int] = None


class QuickEndEvaluator:
    """
    Evaluador desacoplado de condiciones de fin rápido de partida (SRP & OCP).
    Evalúa si se han vendido todas las propiedades del tablero bajo el modo 'ALL_PROPERTIES_SOLD'.
    """

    @classmethod
    def evaluate_after_property_acquired(
        cls,
        game: Game,
        property_repo: PropertyRepositoryProtocol,
        player_repo: PlayerRepositoryProtocol,
        game_repo: GameRepositoryProtocol,
        transaction_repo: Optional[TransactionRepositoryProtocol] = None,
    ) -> QuickEndResult:
        ruleset = game.get_ruleset()
        if ruleset.victory_mode != "ALL_PROPERTIES_SOLD":
            return QuickEndResult(triggered=False, reason="El modo de victoria no es ALL_PROPERTIES_SOLD.")

        if game.status == GameStatus.FINISHED:
            return QuickEndResult(triggered=False, reason="La partida ya se encuentra finalizada.")

        # 1. Obtener todas las casillas comprables del tablero
        board = BoardRuleRegistry.get_board(game.variant)
        purchasable_tiles = {
            tile_id: strategy for tile_id, strategy in board.items()
            if strategy.can_be_purchased()
        }

        # 2. Obtener todas las propiedades que ya tienen dueño
        game_properties = property_repo.list_by_game(game.id)
        owned_tile_ids = {
            p.tile_id for p in game_properties
            if p.owner_id is not None
        }

        # Verificar si todas las casillas comprables tienen dueño
        if not set(purchasable_tiles.keys()).issubset(owned_tile_ids):
            remaining = len(purchasable_tiles) - len(purchasable_tiles.keys() & owned_tile_ids)
            return QuickEndResult(
                triggered=False,
                reason=f"Aún quedan {remaining} propiedades sin dueño en el tablero."
            )

        # 3. ¡Cierre Rápido Activado! Calcular ranking y patrimonio neto
        all_players = player_repo.list_by_game(game.id)
        player_scores = []
        disqualified_ids = []

        val_mode = ruleset.property_valuation_mode.upper()

        for p in all_players:
            props_owned = [prop for prop in game_properties if prop.owner_id == p.id]
            props_val = 0
            bldgs_val = 0
            mortg_debt = 0

            for prop in props_owned:
                strat = purchasable_tiles.get(prop.tile_id)
                if not strat:
                    continue
                defn = strat.definition

                # Valoración de propiedad según modo
                if val_mode == "MORTGAGE_VALUE":
                    base_prop_val = defn.price // 2
                else:
                    base_prop_val = defn.price

                props_val += base_prop_val

                # Valor de edificios
                if prop.houses_count > 0:
                    bldgs_val += prop.houses_count * defn.house_cost
                if prop.hotels_count > 0:
                    bldgs_val += defn.house_cost * 5

                # Si está hipotecada, se descuenta la deuda
                if prop.is_mortgaged:
                    mortg_debt += defn.price // 2

            net_worth = p.money + props_val + bldgs_val - mortg_debt

            # Evaluar elegibilidad
            is_disqualified = False
            disqual_reason = None

            if p.is_bankrupt:
                is_disqualified = True
                disqual_reason = "En bancarrota"
                disqualified_ids.append(p.id)
            elif ruleset.disqualify_jailed_on_quick_end and p.in_jail:
                is_disqualified = True
                disqual_reason = "En la cárcel al momento del cierre rápido"
                disqualified_ids.append(p.id)

            player_scores.append({
                "player_id": p.id,
                "name": p.name,
                "token": p.token,
                "cash": p.money,
                "properties_value": props_val,
                "buildings_value": bldgs_val,
                "mortgage_debt": mortg_debt,
                "net_worth": net_worth,
                "is_in_jail": p.in_jail,
                "is_bankrupt": p.is_bankrupt,
                "is_disqualified": is_disqualified,
                "disqualification_reason": disqual_reason,
            })

        # 4. Determinar ganador:
        # Los jugadores no descalificados tienen prioridad absoluta.
        eligible = [s for s in player_scores if not s["is_disqualified"]]
        disqualified = [s for s in player_scores if s["is_disqualified"]]

        eligible.sort(key=lambda s: s["net_worth"], reverse=True)
        disqualified.sort(key=lambda s: s["net_worth"], reverse=True)

        final_ranking = eligible + disqualified
        for idx, item in enumerate(final_ranking, start=1):
            item["rank"] = idx

        if eligible:
            winner = eligible[0]
            reason_msg = (
                f"🏁 Fin de Partida por Cierre Rápido: Todas las propiedades ({len(purchasable_tiles)}) "
                f"han sido adquiridas. Ganador: {winner['name']} con patrimonio de ${winner['net_worth']}."
            )
        elif player_scores:
            # Caso borde: todos los jugadores activos estaban en la cárcel
            winner = disqualified[0]
            reason_msg = (
                f"🏁 Fin de Partida por Cierre Rápido: Se vendieron todas las propiedades, "
                f"pero todos los jugadores estaban en la cárcel. Desempate por patrimonio: {winner['name']}."
            )
        else:
            winner = None
            reason_msg = "🏁 Fin de Partida por Cierre Rápido sin jugadores válidos."

        # 5. Marcar partida como FINALIZADA
        game.status = GameStatus.FINISHED
        game_repo.save(game)

        # 6. Registrar en el libro contable
        tx_id = None
        if transaction_repo and winner:
            tx = transaction_repo.record(
                Transaction(
                    id=None,
                    game_id=game.id,
                    turn_number=game.current_turn,
                    transaction_type=TransactionType.GAME_FINISHED,
                    amount=winner["net_worth"],
                    description=reason_msg,
                    source_player_id=None,
                    target_player_id=winner["player_id"],
                    tile_id=None,
                )
            )
            tx_id = tx.id

        return QuickEndResult(
            triggered=True,
            winner_id=winner["player_id"] if winner else None,
            winner_name=winner["name"] if winner else None,
            winner_token=winner["token"] if winner else None,
            winner_net_worth=winner["net_worth"] if winner else None,
            rankings=final_ranking,
            disqualified_player_ids=disqualified_ids,
            reason=reason_msg,
            transaction_id=tx_id,
        )
