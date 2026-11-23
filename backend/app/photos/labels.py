"""The damage labels a tech picks a damage photo's description from (design §8).

A placeholder list until the real one arrives. The API rejects any other description,
but the photos.description column stays plain text, so a label retired later still
loads and exports on old claims.
"""

from typing import Literal, get_args

DamageLabel = Literal["Wheel RF", "Wheel LF", "Wheel LR", "Wheel RR"]

# The same labels as a tuple, for sending to the phone: ("Wheel RF", "Wheel LF", ...).
DAMAGE_LABELS: tuple[str, ...] = get_args(DamageLabel)
