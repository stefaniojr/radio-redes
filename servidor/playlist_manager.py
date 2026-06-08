from pathlib import Path
import random

class PlaylistManager:

    def __init__(self):

        self.musicas = sorted(
            Path("audios/musicas").glob("*.mp3")
        )

        self.propagandas = sorted(
            Path("audios/propagandas").glob("*.mp3")
        )

        self.eastereggs = sorted(
            Path("audios/eastereggs").glob("*.mp3")
        )

        self.indice = 0

    def proxima_musica(self):

        faixa = self.musicas[self.indice]

        self.indice = (
            self.indice + 1
        ) % len(self.musicas)

        return faixa

    def proxima_interrupcao(self):

        if random.random() < 0.30:
            return (
                "EASTER_EGG",
                random.choice(
                    self.eastereggs
                )
            )

        return (
            "ADVERTISEMENT",
            random.choice(
                self.propagandas
            )
        )