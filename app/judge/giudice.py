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
        testo = self.conn.execute("SELECT testo FROM regole WHERE titolo = ? AND fonte = ?",
                                  (migliore["titolo"], migliore["fonte"])).fetchone()[0]
        altre = ", ".join(f"«{r['titolo']}»" for r in risultati[1:3])
        risposta = f"{migliore['titolo']}: {' '.join(testo.split())}"
        if altre:
            risposta += f" (Vedi anche {altre}.)"
        return {"risposta": risposta, "fonti": risultati}
