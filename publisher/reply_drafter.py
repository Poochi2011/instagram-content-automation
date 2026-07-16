"""Classifies incoming comments and drafts short template-based replies.

Deliberately rule-based (no LLM, no API cost) so the auto-reply pipeline stays
free to run 24/7. The classifier decides one of three actions per comment:

  reply  -> we draft a short on-voice reply and post it
  flag   -> a human should answer this one personally (crisis language, real
            questions, accusations). Surfaced on the GUI Comments page.
  skip   -> not worth engaging (spam, hostility). Recorded, never answered.

Safety note: this account's niche is recovery/abuse healing, so comments can
include people in genuine distress. Those must NEVER get a cheerful canned
reply — crisis detection runs first and always wins.

Template choice is seeded by the comment id, so a dry-run and the later live
run draft the identical reply, and reruns are stable.
"""

from __future__ import annotations

import random

from database.models import Comment

# ---- Classification word lists (checked against lowercased comment text) ----

_CRISIS_PHRASES = [
    "suicide", "suicidal", "kill myself", "end my life", "want to die",
    "wanna die", "self harm", "self-harm", "hurt myself", "harm myself",
    "no reason to live", "end it all", "can't go on", "cant go on",
    "don't want to live", "dont want to live", "don't want to be here",
    "dont want to be here", "better off dead", "afraid for my life",
    "he will kill me", "she will kill me", "not safe at home",
]

_SPAM_MARKERS = [
    "http://", "https://", "www.", "follow me", "follow back", "check my page",
    "check my profile", "check out my", "free followers", "crypto", "forex",
    "bitcoin", "trading signals", "investment plan", "whatsapp +", "telegram",
    "cashapp", "cash app", "earn from home", "make money online", "dm me for",
]

# Accusations and complaints go to a human — an automated reply here would
# only inflame things (and repost accusations genuinely need her judgement).
_ACCUSATION_MARKERS = [
    "scam", "fake page", "fraud", "stole", "steal", "copied", "copying",
    "reported", "report you", "plagiar", "credit the",
]

_HOSTILE_MARKERS = [
    "stupid", "idiot", "trash", "garbage", "pathetic", "shut up", "nobody cares",
]

_GRATITUDE_MARKERS = [
    "thank you", "thanks", "thankyou", "needed this", "needed to hear",
    "helped me", "helps me", "saved me", "grateful",
]

_QUESTION_STARTERS = (
    "how ", "what ", "where ", "when ", "why ", "who ", "can you", "could you",
    "do you", "does ", "is it", "is this", "are you", "should i", "any advice",
)

# ---- Reply template banks (short, warm, recovery-coach voice) ----

_PRAISE_REPLIES = [
    "So glad this resonated with you \U0001f49b",
    "Thank you for being here — keep shining ✨",
    "This means a lot. Sending you strength \U0001f4aa",
    "Love that you connected with this \U0001f64f",
    "You've got this — one day at a time \U0001f49b",
    "Grateful this found you at the right time ✨",
    "Appreciate you — keep taking care of yourself \U0001f49b",
    "Thank you \U0001f64f healing isn't linear, but you're moving \U0001f331",
]

_GRATITUDE_REPLIES = [
    "You're so welcome \U0001f49b",
    "So glad it helped — you're not alone in this \U0001f64f",
    "Anytime \U0001f49b you're doing better than you think",
    "That's exactly why we share these ✨",
    "Grateful it reached you when you needed it \U0001f49b",
    "Thank you for telling us — keep going \U0001f331",
]

_EMOJI_REPLIES = [
    "\U0001f49b\U0001f49b",
    "Sending love right back \U0001f49b",
    "\U0001f64f✨",
    "Appreciate you \U0001f49b",
    "❤️\U0001f64f",
]

_MENTION_REPLIES = [
    "Thank you for sharing this with someone who might need it \U0001f49b",
    "Love seeing this passed on \U0001f64f",
    "Sharing is caring — thank you \U0001f49b",
]

_REPLY_BANKS = {
    "praise": _PRAISE_REPLIES,
    "gratitude": _GRATITUDE_REPLIES,
    "emoji": _EMOJI_REPLIES,
    "mention": _MENTION_REPLIES,
}

# classification -> action
ACTION_REPLY = "reply"
ACTION_FLAG = "flag"
ACTION_SKIP = "skip"

_CLASSIFICATION_ACTIONS = {
    "crisis": ACTION_FLAG,
    "question": ACTION_FLAG,
    "accusation": ACTION_FLAG,
    "spam": ACTION_SKIP,
    "hostile": ACTION_SKIP,
    "empty": ACTION_SKIP,
    "praise": ACTION_REPLY,
    "gratitude": ACTION_REPLY,
    "emoji": ACTION_REPLY,
    "mention": ACTION_REPLY,
}


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def classify(text: str | None) -> str:
    """Bucket one comment. Order matters: crisis always wins, spam/hostility
    beat the friendly buckets, and 'praise' is the catch-all default."""
    raw = (text or "").strip()
    if not raw:
        return "empty"
    lowered = raw.lower()

    if _contains_any(lowered, _CRISIS_PHRASES):
        return "crisis"
    if _contains_any(lowered, _SPAM_MARKERS):
        return "spam"
    if _contains_any(lowered, _ACCUSATION_MARKERS):
        return "accusation"
    if _contains_any(lowered, _HOSTILE_MARKERS):
        return "hostile"
    if "?" in raw or lowered.startswith(_QUESTION_STARTERS):
        return "question"

    tokens = raw.split()
    if tokens and all(t.startswith("@") for t in tokens):
        return "mention"
    if not any(ch.isalnum() for ch in raw):
        return "emoji"
    if _contains_any(lowered, _GRATITUDE_MARKERS):
        return "gratitude"
    return "praise"


def action_for(classification: str) -> str:
    return _CLASSIFICATION_ACTIONS.get(classification, ACTION_FLAG)


def draft_reply(comment: Comment, classification: str) -> str:
    """Pick a template for a reply-action comment. Seeded by the comment id so
    the draft shown in dry-run is exactly what a later live run posts."""
    bank = _REPLY_BANKS[classification]
    rng = random.Random(comment.ig_comment_id)
    return rng.choice(bank)
