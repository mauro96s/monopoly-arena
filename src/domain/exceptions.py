class DomainException(Exception):
    """Excepción base del dominio de Monopoly."""
    pass


class GameNotFoundError(DomainException):
    """Partida no encontrada."""
    pass


class PlayerNotFoundError(DomainException):
    """Jugador no encontrado."""
    pass


class PropertyNotFoundError(DomainException):
    """Propiedad/Casilla no encontrada en el tablero."""
    pass


class InsufficientFundsError(DomainException):
    """El jugador no cuenta con el dinero necesario para la operación."""
    pass


class PropertyAlreadyOwnedError(DomainException):
    """La propiedad ya tiene un dueño asignado."""
    pass


class InvalidGameActionError(DomainException):
    """La acción solicitada no es válida según las reglas del juego."""
    pass
