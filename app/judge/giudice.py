"""Il giudice risponde citando solo le regole indicizzate: niente risposte inventate."""
from app.judge import indice


class Giudice:
    def __init__(self, conn=None) -> None:
        self.conn = conn or indice.costruisci()

    def rispondi(self, domanda: str) -> dict:
        risultati = indice.cerca(self.conn, domanda)
        if not risultati:
            return {"risposta": "Non trovo regole pertinenti nei testi indicizzati in data/regole.", "fonti": []}
        migliore = risultati[0]
        return {
            "risposta": f"Vedi «{migliore['titolo']}» ({migliore['fonte']}): {migliore['estratto']}",
            "fonti": risultati,
        }
