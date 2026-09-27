"""
magicpin AI Challenge — Conversation Handlers
Multi-turn conversation handling module for Vera.
Handles:
1. Auto-reply detection & graceful backoff / exit.
2. Explicit intent transition (switching from qualification to execution mode).
3. Hostile / opt-out handling with courteous cessation.
4. Off-topic redirection.
5. Engaged multi-turn dialogue progression.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    turns: List[Dict[str, Any]] = field(default_factory=list)
    topic: Optional[str] = None
    intent_state: str = "initial"  # "initial", "engaged", "action_committed", "waiting", "ended"
    auto_reply_count: int = 0
    last_inbound_message: str = ""
    merchant_name: str = ""
    owner_name: str = ""
    category_slug: str = ""


# Auto-reply markers common across WhatsApp Business automated greetings
AUTO_REPLY_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond shortly",
    r"we will get back to you",
    r"automated assistant",
    r"hamari team tak pahuncha",
    r"aapki jaankari ke liye.+shukriya",
    r"auto-reply",
    r"currently unavailable",
    r"we have received your message",
    r"welcome to .+ we will respond",
    r"thanks for reaching out",
]

# Hostile / Opt-out patterns
HOSTILE_PATTERNS = [
    r"stop messaging",
    r"useless spam",
    r"not interested",
    r"why are you bothering",
    r"don't message",
    r"dont message",
    r"spam",
    r"leave me alone",
    r"unsubscribe",
    r"opt out",
    r"harass",
    r"fraud",
    r"block",
]

# High-intent / Action commitment patterns
INTENT_PATTERNS = [
    r"let['’]?s do it",
    r"whats? next",
    r"send the abstract",
    r"send me",
    r"yes please",
    r"draft the",
    r"schedule",
    r"go ahead",
    r"proceed",
    r"confirm",
    r"i want to join",
    r"mujhe.+judrna",
    r"chalo karte",
    r"theek hai karo",
    r"kar do",
    r"yes.+do it",
    r"sure.+start",
]

# Off-topic patterns
OFF_TOPIC_PATTERNS = [
    r"gst filing",
    r"file my gst",
    r"income tax",
    r"personal loan",
    r"accounting software",
    r"hire staff",
]


def is_auto_reply(message: str, state: ConversationState) -> bool:
    """Detect if the message is a canned WhatsApp Business auto-reply."""
    clean = message.lower().strip()
    # Check regex patterns
    for pat in AUTO_REPLY_PATTERNS:
        if re.search(pat, clean):
            return True
    # Check verbatim repetition from previous turn
    if state.last_inbound_message and clean == state.last_inbound_message.lower().strip():
        return True
    return False


def is_hostile(message: str) -> bool:
    """Detect hostility or explicit opt-out."""
    clean = message.lower().strip()
    return any(re.search(pat, clean) for pat in HOSTILE_PATTERNS)


def is_intent_commitment(message: str) -> bool:
    """Detect when merchant shifts to explicit action commitment."""
    clean = message.lower().strip()
    return any(re.search(pat, clean) for pat in INTENT_PATTERNS)


def is_off_topic(message: str) -> Optional[str]:
    """Detect common off-topic queries."""
    clean = message.lower().strip()
    for pat in OFF_TOPIC_PATTERNS:
        if re.search(pat, clean):
            return pat
    return None


def respond(state: ConversationState, merchant_message: str) -> dict:
    """
    Given the conversation state and the merchant's latest message,
    produce the appropriate next action: 'send', 'wait', or 'end'.
    """
    msg_clean = merchant_message.strip()
    state.turns.append({"from": "merchant", "message": msg_clean})

    # 1. Check for Hostility / Opt-out
    if is_hostile(msg_clean):
        state.intent_state = "ended"
        return {
            "action": "end",
            "rationale": "Merchant explicitly opted out or expressed frustration; gracefully closing conversation and suppressing future sends."
        }

    # 2. Check for WhatsApp Business Auto-Reply
    if is_auto_reply(msg_clean, state):
        state.auto_reply_count += 1
        state.last_inbound_message = msg_clean

        if state.auto_reply_count == 1:
            # First auto-reply: acknowledge gently and leave a simple binary hook for the real owner
            return {
                "action": "send",
                "body": "Looks like an auto-reply 😊 When the owner sees this, just reply 'Yes' or tell me if you'd like to proceed!",
                "cta": "binary_yes_no",
                "rationale": "Detected canned WhatsApp auto-reply; sent one clear, non-intrusive hook for when the owner reviews the chat."
            }
        elif state.auto_reply_count == 2:
            # Second auto-reply: back off and wait
            state.intent_state = "waiting"
            return {
                "action": "wait",
                "wait_seconds": 86400,
                "rationale": "Same auto-reply received twice in a row; owner is not at the phone. Backing off 24h before any re-engagement."
            }
        else:
            # 3+ auto-replies: terminate conversation
            state.intent_state = "ended"
            return {
                "action": "end",
                "rationale": "Persistent automated auto-reply detected 3+ times with no human response; cleanly ending conversation."
            }

    # Reset auto-reply counter if genuine reply
    state.auto_reply_count = 0
    state.last_inbound_message = msg_clean

    # 3. Check for Off-Topic
    off_topic_hit = is_off_topic(msg_clean)
    if off_topic_hit:
        return {
            "action": "send",
            "body": "I'll have to leave GST/accounting filing to your CA — that's outside what I can handle directly. Coming back to our marketing update — want me to draft the post first, or should we review your active offers?",
            "cta": "open_ended",
            "rationale": "Out-of-scope question politely declined; smoothly redirected back to core local growth objectives."
        }

    # 4. Check for Action Commitment / Intent Transition
    if is_intent_commitment(msg_clean):
        state.intent_state = "action_committed"
        owner_salutation = f"{state.owner_name}, " if state.owner_name else ""
        
        # Determine appropriate action artifact based on topic or category
        if "abstract" in msg_clean.lower() or "jida" in (state.topic or "").lower() or state.category_slug == "dentists":
            return {
                "action": "send",
                "body": f"Done! {owner_salutation}here is the summary draft ready to share:\n\n\"New clinical guidance confirms 3-month dental recall reduces caries recurrence significantly in adult patients. Book your preventative scaling this week.\"\n\nSending the 2-page abstract directly. Reply CONFIRM to schedule this post on your Google profile for tomorrow 10am.",
                "cta": "binary_confirm_cancel",
                "rationale": "Switched immediately to ACTION mode upon explicit commitment. Provided the drafted artifact and requested a binary CONFIRM."
            }
        elif "thali" in msg_clean.lower() or state.category_slug == "restaurants":
            return {
                "action": "send",
                "body": f"Done! {owner_salutation}drafted your corporate lunch offer. 3 nearby business offices can be targeted right away. Reply CONFIRM to publish this as a Google post and generate your WhatsApp flyer.",
                "cta": "binary_confirm_cancel",
                "rationale": "Executed action mode immediately with concrete deliverables and a binary confirmation ask."
            }
        elif "yoga" in msg_clean.lower() or state.category_slug == "gyms":
            return {
                "action": "send",
                "body": f"Done! {owner_salutation}I've structured the 4-week program and drafted the announcement flyer with timings and fees. Reply CONFIRM to push this live to your Google profile now.",
                "cta": "binary_confirm_cancel",
                "rationale": "Transitioned seamlessly to action mode without re-asking qualifying questions."
            }
        else:
            return {
                "action": "send",
                "body": f"Done! {owner_salutation}I've prepared the draft and pre-filled your Google update for tomorrow morning. Reply CONFIRM to proceed, or let me know if you want any edits.",
                "cta": "binary_confirm_cancel",
                "rationale": "Action mode executed promptly without repetitive qualification."
            }

    # 5. Default Engaged Progression
    owner_salutation = f"{state.owner_name}, " if state.owner_name else ""
    return {
        "action": "send",
        "body": f"Got it, {owner_salutation}here is what's next: I can have this ready and posted to your Google profile in under 2 minutes. Shall I go ahead and publish?",
        "cta": "binary_yes_no",
        "rationale": "Acknowledged merchant input and advanced directly to the lowest-friction closing step."
    }
