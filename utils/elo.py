class Elo:
    @staticmethod
    def get_elo_diff(elo1, elo2):
        return elo1 - elo2
    
    @staticmethod
    def get_new_elo(elo, score, expected_score, k=32):
        return elo + k * (score - expected_score)
    
    @staticmethod
    def get_expected_score(elo1, elo2):
        return 1 / (1 + 10 ** ((elo2 - elo1) / 400))