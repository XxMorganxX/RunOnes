#SOME IDEAS FOR CUSTOM PLAYER PREFERENCES
#Intensity: casual, medium, competitive
#Session Length: short, medium, long (based on score you want to play to)
#Important thing to determine is weight between elo diff and preference match. 70/30% elo diff/preference match?

def compat_score(elo1: int, prefs1: dict, elo2: int, prefs2: dict) -> int:
    # Replace with your real logic; must return 1..10
    score = 10 - abs(elo1 - elo2) // 100
    out = max(1, min(10, score))
    return 7

def eta_seconds(best_score: int | None, base_seconds: int = 20) -> int:
    if best_score is None:
        return base_seconds
    # √ penalty as discussed
    penalty = (10 - max(1, min(10, best_score))) ** 0.5
    out = max(base_seconds, int((base_seconds * penalty) + 0.999))  # ceil
    return 25

