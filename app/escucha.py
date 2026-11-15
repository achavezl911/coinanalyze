"""Los segundos que un colector NO escucho a un venue por una reconexion (DATOS A, A2).

`segundos_cubiertos` conocia el arranque y la parada del proceso, pero no los cortes de en
medio: si el websocket de un venue caia en el segundo 20 de un minuto y volvia en el 56, la
fila de ese minuto decia covered_seconds=60 con 36 s sin oir nada (hallazgo F3-F1). Aqui
cada consumidor apunta cuando dejo de oir y cuando volvio, y el escritor del minuto resta
esos intervalos.

El corte empieza en el ULTIMO mensaje oido y no en el instante en que se detecta: un
`wait_for(..., 60)` que vence o un ping sin pong se ven tarde, y lo que hubo entre medias no
se oyo. La vuelta es el instante en que la conexion (y su suscripcion) queda abierta.
"""

from __future__ import annotations

import time

# Los minutos se escriben al cerrar mas una gracia de ~2 min; una hora sobra.
PODA_SEGUNDOS = 3600.0


class Escucha:
    """Intervalos [corte, vuelta) en hora de pared en que un venue no se escuchaba.

    Un corte abierto (vuelta None) dura hasta ahora: el minuto que se escribe con el venue aun
    caido cuenta como no oido todo lo que va desde el corte.
    """

    def __init__(self) -> None:
        self._cortes: list[list[float | None]] = []
        self._ultimo: float | None = None

    def oido(self, t: float | None = None) -> None:
        self._ultimo = time.time() if t is None else t

    def vuelta(self, t: float | None = None) -> None:
        ahora = time.time() if t is None else t
        self._ultimo = ahora
        if self._cortes and self._cortes[-1][1] is None:
            self._cortes[-1][1] = ahora

    def corte(self, t: float | None = None) -> None:
        if self._cortes and self._cortes[-1][1] is None:
            return  # ya estaba cortado: un reintento fallido no abre otro corte
        ahora = time.time() if t is None else t
        desde = ahora if self._ultimo is None else min(ahora, self._ultimo)
        self._cortes = [c for c in self._cortes if c[1] is not None and c[1] > ahora - PODA_SEGUNDOS]
        self._cortes.append([desde, None])

    def cortes(self) -> tuple[tuple[float, float | None], ...]:
        return tuple((float(c[0]), c[1]) for c in self._cortes)  # type: ignore[arg-type]


def segundos_sin_oir(desde: float, hasta: float, cortes) -> float:
    """Cuanto de [desde, hasta) cae dentro de algun corte."""
    total = 0.0
    for inicio, vuelta in cortes:
        a = max(desde, inicio)
        b = hasta if vuelta is None else min(hasta, vuelta)
        if b > a:
            total += b - a
    return total
