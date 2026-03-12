import re

BAD_WORDS = {"badword", "shit", "fuck", "damn", "bitch"}

def normalize(text):
    return re.sub(r"[^a-zA-Z0-9 ]", "", text.lower())

def detect_bad_words(text):
    normalized = normalize(text)
    found = [w for w in BAD_WORDS if w in normalized]
    return found

def is_blocked(text):
    return bool(detect_bad_words(text))
    return bool(result["profanity"] or result["hate_speech"])