"""The gear catalogue: what every new item is, derived from the tier numbers.

Design rules (from the user):
  * Every item from tier 60 up has one MAJOR stat and at least one MINOR stat; tier 80+ adds
    a second minor, and the minors grow every tier. Single stats hit the 999 cap easily at
    high tiers, so the growth has to land on the *other* stats for upgrades to matter.
  * Accuracy is standard on every weapon - damage is worthless if it misses.
  * SP (the MP field) is standard on all equipment from tier 70, and SP regeneration
    becomes common from tier 80 (every weapon and armour piece, several accessories).
  * Accessories never exceed 2.5 x danger in total stat points (HP counted at a tenth,
    SP at a half). Checked by `accessory_points` and asserted in `design`.
  * Once Atk / Elem. Atk reach 999, power has to come from effects instead: on-hit procs
    ("target takes 50% more damage" multiplies after the cap), double strikes, crit-or-miss,
    instant death, elemental boosts, status immunity, regen.
  * Only effects shipped equipment already uses. Two-plus effects on one piece is proven by
    the shipped Thunder+Ice axe and the HP+SP-regen shield; proc chance (DiseaseRate) and
    duration (InvocationTurn) vary per item in shipped data (5-10%, 2-5 turns).
  * Every description states every stat and effect exactly; validate.py regenerates each
    description from the item's real row data and requires an exact match.
"""

TIERS = [60, 70, 80, 90, 99, 104]
TIER_NAME = {60: "Tempered", 70: "Runeforged", 80: "Astral", 90: "Sovereign", 99: "Eternal",
             104: "Mythic"}

# growth of the secondary stats, as a fraction of the major stat
MINOR1 = {60: 0.30, 70: 0.35, 80: 0.40, 90: 0.45, 99: 0.50}
MINOR2 = {60: 0.00, 70: 0.00, 80: 0.25, 90: 0.30, 99: 0.35}
# flat SP on every weapon/armour piece; zero at tier 60 except on SP-flavoured pieces
# flat SP per armour slot (x2 on shield/body, x3 on head - weapons carry none). Sized so a
# caster can sustain 75-SP double casts: ~420 SP from armour at tier 70, ~1,680 at 99.
SP_STD = {60: 20, 70: 60, 80: 110, 90: 170, 99: 240}
# flat accuracy on every weapon
ACC_STD = {60: 80, 70: 110, 80: 140, 90: 170, 99: 200}
# SP restored after every action (shipped gear: 8 on the best shield)
SP_REGEN_ARMOUR = {80: 4, 90: 6, 99: 8}
SP_REGEN_CASTER = {80: 8, 90: 12, 99: 16}
BRUTAL_MULT_BONUS = 15
SECONDARY_REF = 714     # weapon secondary stats scale off at most this much attack

# ---- on-hit procs: chance (%) and duration (turns) by tier ----------------------------
# Shipped weapons use 5-10% for 4-5 turns.
PROC_CHANCE = {70: 15, 80: 25, 90: 35, 99: 50}
PROC_TURNS = {70: 4, 80: 4, 90: 5, 99: 5}
HEX_CHANCE = {70: 20, 80: 30, 90: 40, 99: 50}          # status ailments
GAMBLE_CRIT = {80: 70, 90: 75, 99: 80}                 # shipped: 65
DEATH_CHANCE = {80: 8, 90: 12, 99: 15}                 # shipped: 5
# what each weapon flavour inflicts on hit
FLAVOUR_PROC = {"Keen": "ADD_DEF_DOWN", "Arcane": "ADD_MDEF_DOWN", "Swift": "ADD_AGI_DOWN",
                "Brutal": "ADD_ATK_DOWN", "Sage": "ADD_MATK_DOWN",
                "Quicksilver": "ADD_AGI_DOWN", "Battle": "ADD_DEF_DOWN",
                "Ruinous": "ADD_MDEF_DOWN"}
HEX_WEAPONS = [("Venom", "dagger", "ADD_POISON_NORMAL"),
               ("Dreaming", "bow", "ADD_SLEEP_NORMAL"),
               ("Blinding", "lance", "ADD_BLIND_NORMAL"),
               ("Maddening", "rod", "ADD_CONFUSION_NORMAL")]
DUAL_ELEMENT_WEAPONS = [("Frostfire", "FIRE", "ICE", "axe"),
                        ("Stormwind", "THUNDER", "WIND", "bow"),
                        ("Twilight", "LIGHT", "DARK", "dagger")]
# DISABLED after an in-game test (2026-10-05): with these buffs on an accessory worn by the
# whole party there was no Speed / Elem. Def-up icon, BP stayed at the normal +1 per turn and
# HP did not regenerate. The game only honours certain effect types from equipment (fixed
# HP/SP regen, resistances, elemental / weapon boosts); general battle buffs are ignored.
# Kept for the record and in case a later test finds one that works.
RELICS_ENABLED = False
# Relics: one battle buff each, worn permanently (-1 turns, the timing shipped gear uses for
# regen). The data-only stand-in for extra support-skill slots. Magnitudes are the game's
# own (from the skills that grant them): +50% damage / Speed, -33% Elemental damage taken,
# 10% HP regen, 2 BP per turn when not boosting, 25% damage nullify, always-crit spells.
# name, effect, value, from tier, major stat, minor stat
RELICS = [
    ("Relic of Renewal", "ADD_HP_REGENERATION", 10, 70, "HP", "MDEF"),
    ("Relic of Haste", "ADD_AGI_UP", 0, 70, "AGI", "EVA"),
    ("Relic of Sanctuary", "ADD_MDEF_UP", 0, 70, "MDEF", "HP"),
    ("Relic of Might", "ADD_ATK_UP", 0, 80, "ATK", "ACC"),
    ("Relic of Sorcery", "ADD_MATK_UP", 0, 80, "MATK", "MP"),
    ("Relic of Fortune", "ADD_PARMNENT_CRITICAL", 0, 80, "CON", "ACC"),
    ("Relic of Momentum", "ADD_BP_REGENERATION", 1, 90, "AGI", "HP"),
    ("Relic of Providence", "ADD_DIVINE_PROTECT", 25, 90, "HP", "DEF"),
    ("Relic of the Arcanum", "ADD_MAGIC_CRITICAL", 0, 99, "MATK", "MP"),
    ("Relic of Rebirth", "ADD_RERAISE", 0, 99, "HP", "MDEF"),
]
RELIC_TEXT = {
    "ADD_AGI_UP": "Speed +50%",
    "ADD_MDEF_UP": "Elemental damage taken -33%",
    "ADD_ATK_UP": "Physical damage dealt +50%",
    "ADD_MATK_UP": "Elemental damage dealt +50%",
    "ADD_PARMNENT_CRITICAL": "raised critical hit rate",
    "ADD_BP_REGENERATION": "gain 2 BP per turn when not boosting",
    "ADD_MAGIC_CRITICAL": "Elemental attacks always critical (+25%)",
    "ADD_RERAISE": "revive automatically when knocked out",
}
# Healing power comes from Elemental Defense, so healers want it as a MAIN stat that grows
# with the tier like an attack stat, not as a capped secondary.
HALLOWED_WEAPONS = [("rod", "Staff"), ("axe", "Axe")]

TALISMANS = [  # name, immunities, major, minor, from tier
    ("Talisman of Clarity", ("Sleep", "Confusion", "Terror"), "MDEF", "AGI", 60),
    ("Talisman of Purity", ("Poison", "Blindness", "Silence"), "DEF", "HP", 60),
    ("Talisman of Life", ("Unconsciousness", "Instant Death"), "HP", "MDEF", 80),
    ("Panacea Talisman", ("Poison", "Silence", "Blindness", "Confusion", "Sleep", "Terror",
                          "Unconsciousness", "Instant Death"), "HP", "DEF", 99),
]

WEAPON_TYPES = [("sword", "ITM_WS_045", "Blade"), ("lance", "ITM_WL_045", "Spear"),
                ("dagger", "ITM_WD_045", "Dagger"), ("axe", "ITM_WA_048", "Axe"),
                ("bow", "ITM_WB_045", "Bow"), ("rod", "ITM_WR_045", "Staff")]
ARMOUR_SLOTS = [("shield", "ITM_AS_035", "Shield"), ("head", "ITM_AH_024", "Helm"),
                ("body", "ITM_AB_024", "Mail")]
ACCESSORY_TEMPLATE = "ITM_AC_033"
ELEMENTS = [("Fire", "FIRE_ABILITY_UP", "FIRE_RESIST", "sword"),
            ("Ice", "ICE_ABILITY_UP", "ICE_RESIST", "axe"),
            ("Thunder", "THUNDER_ABILITY_UP", "THUNDER_RESIST", "lance"),
            ("Wind", "WIND_ABILITY_UP", "WIND_RESIST", "bow"),
            ("Light", "LIGHT_ABILITY_UP", "LIGHT_RESIST", "dagger"),
            ("Dark", "DARK_ABILITY_UP", "DARK_RESIST", "axe")]
ELEM_WEAPON_PCT = {70: 130, 80: 140, 90: 150, 99: 160}
SIGIL_PCT = {70: 115, 80: 120, 90: 130, 99: 140}
WARD_RESIST = {70: 75, 80: 50, 90: 25, 99: 1}          # lower = stronger (shipped: 75/50/1)
DUAL_WARDS = [("Fire", "Ice"), ("Thunder", "Wind"), ("Light", "Dark")]

# name, major, minor1, minor2
CHARMS = [
    ("Charm of Might", "ATK", "ACC", "CON"),
    ("Charm of Precision", "CON", "ACC", "ATK"),
    ("Charm of Sorcery", "MATK", "MDEF", "AGI"),
    ("Charm of the Bulwark", "DEF", "HP", "MDEF"),
    ("Charm of the Aegis", "MDEF", "DEF", "HP"),
    ("Charm of Celerity", "AGI", "EVA", "ACC"),
    ("Charm of Shadows", "EVA", "AGI", "CON"),
    ("Charm of Spirit", "MP", "MATK", "MDEF"),
    ("Charm of Vitality", "HP", "DEF", "MP"),
]
# name, effect, value by tier, major stat, minor stat
PASSIVES = [
    ("Pendant of Renewal", "ADD_MP_FIXED_REGENERATION",
     {60: 6, 70: 8, 80: 12, 90: 16, 99: 20}, "MP", "MATK"),
    ("Pendant of Mending", "ADD_HP_FIXED_REGENERATION",
     {60: 150, 70: 220, 80: 300, 90: 500, 99: 800}, "HP", "DEF"),
    ("Scholar's Token", "JPUP", {60: 125, 70: 140, 80: 150, 90: 175, 99: 200}, "CON", "ACC"),
    ("Wayfarer's Token", "EXPUP", {60: 125, 70: 140, 80: 150, 90: 175, 99: 200}, "AGI", "EVA"),
]
PASSIVE_VALUES = {p[1]: p[2] for p in PASSIVES}

# accessory point weights: HP is plentiful, SP is scarce
WEIGHT = {"HP": 0.1, "MP": 0.5}

SP_SINGLE_TEMPLATE = "ITM_087"      # Inspiriting Plum (M)  - one ally
SP_GROUP_TEMPLATE = "ITM_088"       # Inspiriting Plum Basket - whole party
SP_SINGLE_AMOUNT = 500
SP_GROUP_AMOUNT = 300
SP_SINGLE_PRICE = 8000
SP_GROUP_PRICE = 24000
VITAL_SINGLE_TEMPLATE = "ITM_007"   # Revitalizing Jam - one ally, HP+SP 100%
VITAL_GROUP_TEMPLATE = "ITM_080"    # Healing Grape bunch - whole party
VITAL_SINGLE_PCT = 50
VITAL_GROUP_PCT = 35
VITAL_SINGLE_PRICE = 6000
VITAL_GROUP_PRICE = 18000
# XL soulstones: one more rung above the shipped (L) ones (2,700 to all foes), for worlds
# where foes have 20,000+ HP. Sold - and reached by drop upgrades - from tier 70.
SOULSTONE_XL = [("Fire", "ITM_137"), ("Ice", "ITM_138"), ("Thunder", "ITM_139"),
                ("Wind", "ITM_140"), ("Light", "ITM_141"), ("Shadow", "ITM_142")]
SOULSTONE_XL_DAMAGE = 9000
SOULSTONE_XL_PRICE = 20000
SOULSTONE_XL_TIER = 70


def accessory_points(stats):
    """Total boost as the 2.5 x danger rule counts it (penalties don't refund points)."""
    return sum(max(0, v) * WEIGHT.get(s, 1.0) for s, v in stats.items())


def _from_points(stat, pts):
    """Points -> raw stat value under the accessory weighting."""
    return int(pts / WEIGHT.get(stat, 1.0))


def _clean(stats):
    out = {}
    for k, v in stats.items():
        v = int(round(v))
        if v:
            out[k] = out.get(k, 0) + v
    return out


# ---- descriptions ----------------------------------------------------------------------
# Wording matches BetterDescriptions_p.pak so new gear reads like the rest of the game.
# Lines are separated by a LITERAL backslash-n (two characters), exactly as shipped text does.
NL = "\\" + "n"
STAT_TEXT = {"ATK": "Phys. Atk.", "MATK": "Elem. Atk.", "DEF": "Phys. Def.",
             "MDEF": "Elem. Def.", "ACC": "Accuracy", "EVA": "Evasion", "CON": "Critical",
             "AGI": "Speed", "HP": "Max. HP", "MP": "Max. SP"}
STAT_ORDER = ["ATK", "MATK", "DEF", "MDEF", "ACC", "EVA", "CON", "AGI", "HP", "MP"]
ELEMENT_TEXT = {"FIRE": "Fire", "ICE": "Ice", "THUNDER": "Lightning", "WIND": "Wind",
                "LIGHT": "Light", "DARK": "Dark"}
# shipped descriptions never exceed three lines (longest line 113 chars); stay inside that
MAX_LINES = 3
MAX_LINE_CHARS = 120
IMMUNITY_ORDER = ["Poison", "Silence", "Blindness", "Confusion", "Sleep", "Terror",
                  "Unconsciousness", "Instant Death"]
# on-hit effects: what happens to the target (magnitudes from the shipped descriptions)
DEBUFF_TEXT = {
    "ADD_DEF_DOWN": "target takes 50% more Physical damage",
    "ADD_MDEF_DOWN": "target takes 50% more Elemental damage",
    "ADD_ATK_DOWN": "target deals 33% less Physical damage",
    "ADD_MATK_DOWN": "target deals 33% less Elemental damage",
    "ADD_AGI_DOWN": "target's Speed falls 33%",
    "ADD_EVA_DOWN": "target's Evasion falls 33%",
    "ADD_ACC_DOWN": "target's Accuracy falls 33%",
    "ADD_POISON_NORMAL": "to inflict Poison",
    "ADD_SLEEP_NORMAL": "to inflict Sleep",
    "ADD_BLIND_NORMAL": "to inflict Blindness",
    "ADD_CONFUSION_NORMAL": "to inflict Confusion",
}


def _join(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def _timing(entry):
    """(name, value[, turn, rate]) -> (name, value, turn, rate)."""
    if len(entry) == 4:
        return tuple(entry)
    from make_gear import AILMENT_TIMING
    return (entry[0], entry[1]) + AILMENT_TIMING.get(entry[0], (0, 0))


def describe(stats, ails, immune=()):
    """Exact stats and effects, in at most three lines. validate.py calls this on each
    item's real row data and requires the shipped description to match exactly."""
    ails = [_timing(a) for a in ails]
    parts = [f"{STAT_TEXT[s]} {stats[s]:+d}" for s in STAT_ORDER if stats.get(s)]
    attack, equip = [], []
    up, res, regen, procs, gains = {}, {}, {}, {}, {}
    for a, v, turn, rate in ails:
        if a == "WEAPON_ABILITY_UP":
            attack.append(f"+{v - 100}% Physical damage (stacks across weapons)")
        elif a == "DOUBLE_HIT":
            attack.append("every regular attack hits twice")
        elif a == "HIT_OR_MISS":
            attack.append(f"{v}% chance to land a Critical hit, otherwise it misses")
        elif a == "INSTANT_DEATH":
            attack.append(f"{rate}% chance of an instant kill")
        elif a in DEBUFF_TEXT:
            procs.setdefault((rate, turn), []).append(a)
        elif a.endswith("_ABILITY_UP"):
            up.setdefault(v, []).append(ELEMENT_TEXT[a.split("_")[0]])
        elif a.endswith("_RESIST"):
            res.setdefault(v, []).append(ELEMENT_TEXT[a.split("_")[0]])
        elif a == "ADD_MP_FIXED_REGENERATION":
            regen["SP"] = v
        elif a == "ADD_HP_FIXED_REGENERATION":
            regen["HP"] = v
        elif a in ("EXPUP", "JPUP"):
            gains[a] = v
        elif a == "ADD_HP_REGENERATION":
            equip.append(f"restores {v}% HP after every turn")
        elif a == "ADD_DIVINE_PROTECT":
            equip.append(f"{v}% chance to nullify all damage")
        elif a in RELIC_TEXT:
            equip.append(RELIC_TEXT[a])
        elif a == "ENCOUNT_UP" and v == 2:
            equip.append("doubles encounter rate")
        else:
            raise ValueError(f"no description wording for effect {a}={v}")
    for (rate, turn), names in procs.items():
        dur = f" ({turn} turns)" if turn > 0 else ""
        if len(names) == 1:
            attack.append(f"{rate}% chance {DEBUFF_TEXT[names[0]]}{dur}")
        elif sorted(names) == ["ADD_DEF_DOWN", "ADD_MDEF_DOWN"]:
            attack.append(f"{rate}% chance each: target takes 50% more Physical / Elemental "
                          f"damage{dur}")
        else:
            attack.append(f"{rate}% chance each: " + "; ".join(DEBUFF_TEXT[n] for n in names)
                          + dur)
    # JP-up gear also raises battle money by the same amount (blueprint_patch.py)
    if gains.get("EXPUP") is not None and gains.get("EXPUP") == gains.get("JPUP"):
        equip.append(f"+{gains['EXPUP'] - 100}% party EXP, JP and money "
                     f"(JP/money: best one counts)")
    else:
        for a, label in (("EXPUP", "party EXP"),
                         ("JPUP", "party JP and money (best one counts)")):
            if a in gains:
                equip.append(f"+{gains[a] - 100}% {label}")
    # How these combine was read from BattlePlayerBP: each element's boosts are summed over
    # every equipped piece (100% + sum of (value - 100)) and the total multiplies the hit
    # after skills and buffs; resistances sum the same way, down to 0% (immune).
    boosts = [f"+{v - 100}% {_join(els)} damage dealt" for v, els in up.items()]
    boosts += [f"-{100 - v}% {_join(els)} damage taken" for v, els in res.items()]
    if boosts:
        boosts[-1] += (" (each stacks with all gear and skills)" if len(boosts) > 1
                       else " (stacks with all gear and skills)")
        equip += boosts
    if regen:
        what = _join([f"{regen[k]} {k}" for k in ("HP", "SP") if k in regen])
        equip.append(f"restores {what} after every turn")
    if immune and set(IMMUNITY_ORDER) <= set(immune):
        equip.append("prevents all status ailments and Instant Death")
    elif immune:
        equip.append("prevents " + _join([s for s in IMMUNITY_ORDER if s in immune]))

    def cap(x):
        return x[0].upper() + x[1:]
    eff = []
    if attack:
        eff.append("Attack: " + cap("; ".join(attack)))
    if equip:
        eff.append("Equip: " + cap(", ".join(equip)))
    # the same effects with a long Equip line wrapped onto a second line
    wrapped = list(eff)
    if equip and len(equip) > 1:
        cut = max(1, len(equip) // 2)
        wrapped[-1:] = ["Equip: " + cap(", ".join(equip[:cut])),
                        cap(", ".join(equip[cut:]))]

    def fits(lines):
        return len(lines) <= MAX_LINES and all(len(x) <= MAX_LINE_CHARS for x in lines)
    # as few stat lines as fit, effects on their own lines; merge the effects if needed
    for tail in (eff, [". ".join(eff)] if eff else [], wrapped):
        for per in (4, 5, 3, 10):
            lines = [", ".join(parts[i:i + per]) for i in range(0, len(parts), per)] + tail
            if fits(lines):
                return NL.join(lines)
    raise AssertionError(f"description will not fit in {MAX_LINES} lines: {parts} / {eff}")


# ---- the catalogue ---------------------------------------------------------------------
def _extend_tier(new=104, base=99, prev=90):
    """Give every per-tier table a value for the Mythic tier (danger 104, past the level cap,
    for the Gate of Finis): its 90 -> 99 step carried on to 104. Chances stay <= 100 and
    resistances can't pass full immunity."""
    capped = {"PROC_CHANCE": 100, "HEX_CHANCE": 100, "GAMBLE_CRIT": 100, "DEATH_CHANCE": 100}

    def grow(d, name=""):
        if base not in d or new in d:
            return
        v = d[base]
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            d[new] = v
            return
        step = (v - d[prev]) * (new - base) / (base - prev) if prev in d else 0
        x = v + step
        if name == "WARD_RESIST":
            x = max(1, x)
        if name in capped:
            x = min(capped[name], x)
        d[new] = round(x, 3) if isinstance(v, float) else int(round(x))

    def walk(obj, name=""):
        if isinstance(obj, dict):
            if obj and all(isinstance(k, int) for k in obj):
                grow(obj, name)
        elif isinstance(obj, (list, tuple)):
            for x in obj:
                walk(x, name)
    for name, obj in list(globals().items()):
        if name.isupper() and name not in ("TIERS", "TIER_NAME"):
            walk(obj, name)


_extend_tier()


def design(nums):
    """nums: tier -> dict(weapon_atk, weapon_mult, def_slot, hp_slot, budget, price)."""
    out = []

    def add(T, kind, template, name, stats, ails, price, immune=()):
        stats = _clean(stats)
        ails = [a for a in ails if not (a[0] == "WEAPON_ABILITY_UP" and a[1] <= 100)]
        # SP regen is standard on every tier 80+ accessory (user: common at 80/90). Weapons
        # carry none - it does nothing there.
        if (kind == "accessory" and T >= 80 and len(ails) < 4
                and not any(a[0] == "ADD_MP_FIXED_REGENERATION" for a in ails)):
            ails = ails + [("ADD_MP_FIXED_REGENERATION", SP_REGEN_ARMOUR[T])]
        majors = [s for s, v in stats.items() if v > 0]
        if kind != "consumable" and len(majors) < 2:
            raise AssertionError(f"{name}: needs a major and a minor stat, has {stats}")
        if kind == "accessory":
            pts = accessory_points(stats)
            if pts > 2.5 * T + 0.5:
                raise AssertionError(f"{name}: {pts:.0f} points > 2.5 x {T}")
        out.append(dict(tier=T, kind=kind, template=template, name=name, stats=stats,
                        ailment=ails, price=int(price), immune=tuple(immune),
                        desc=describe(stats, ails, immune)))

    tmpl_of = {s: (t, nn) for s, t, nn in WEAPON_TYPES}
    for T in TIERS:
        n = nums[T]
        pre = TIER_NAME[T]
        W, M, D, H = n["weapon_atk"], n["weapon_mult"], n["def_slot"], n["hp_slot"]
        m1, m2, sp, acc = MINOR1[T], MINOR2[T], SP_STD[T], ACC_STD[T]
        # reference for weapon SECONDARY stats: the attack stat stopped being capped, but
        # enemy Evasion / Speed never scale, so Critical / Accuracy / Speed must not follow it
        Ws = min(W, SECONDARY_REF)
        price = n["price"]
        B = 2.5 * T
        caster_regen = [("ADD_MP_FIXED_REGENERATION", SP_REGEN_CASTER[T])] if T >= 80 else []
        armour_regen = [("ADD_MP_FIXED_REGENERATION", SP_REGEN_ARMOUR[T])] if T >= 80 else []

        def proc(name, scale=1.0, chance=None, turns=None):
            """An on-hit effect from tier 70: (name, 0, turns, % chance)."""
            if T < 70:
                return []
            c = chance if chance is not None else PROC_CHANCE[T]
            return [(name, 0, turns if turns is not None else PROC_TURNS[T],
                     max(1, int(round(c * scale))))]

        # ---- weapons: four flavours per type, each with its own on-hit effect ----
        for slot, tmpl, noun in WEAPON_TYPES:
            if slot == "rod":
                flav = [
                    ("Sage", {"MATK": W, "MDEF": m1 * Ws,
                              "ACC": acc, "AGI": m2 * Ws}, M, []),
                    ("Quicksilver", {"MATK": 0.9 * W, "AGI": m1 * Ws, "EVA": m2 * Ws,
                                     "ACC": acc}, M, []),
                    ("Battle", {"MATK": 0.8 * W, "ATK": (m1 + 0.2) * W, "DEF": m2 * Ws,
                                "ACC": acc}, M, []),
                    ("Ruinous", {"MATK": W, "MDEF": m1 * Ws, "AGI": m2 * Ws,
                                 "ACC": acc}, M + BRUTAL_MULT_BONUS, []),
                ]
            else:
                flav = [
                    ("Keen", {"ATK": W, "CON": m1 * Ws, "ACC": acc + m2 * Ws},
                     M, []),
                    ("Swift", {"ATK": 0.9 * W, "AGI": m1 * Ws, "EVA": m2 * Ws,
                               "ACC": acc}, M, []),
                    ("Arcane", {"ATK": 0.8 * W, "MATK": (m1 + 0.2) * W, "MDEF": m2 * Ws,
                                "ACC": acc}, M, []),
                    ("Brutal", {"ATK": W, "DEF": m1 * Ws, "CON": m2 * Ws,
                                "ACC": acc}, M + BRUTAL_MULT_BONUS, []),
                ]
            for fname, stats, mult, extra in flav:
                add(T, "weapon", tmpl, f"{pre} {fname} {noun}", stats,
                    [("WEAPON_ABILITY_UP", mult)] + proc(FLAVOUR_PROC[fname]) + extra, price)

        # ---- healer weapons: Elemental Defense (healing power) as the main stat ----
        for slot, noun in HALLOWED_WEAPONS:
            tmpl, _n = tmpl_of[slot]
            main = "MATK" if slot == "rod" else "ATK"
            add(T, "weapon", tmpl, f"{pre} Hallowed {noun}",
                {"MDEF": W, main: 0.6 * W, "ACC": acc, "AGI": m2 * Ws},
                [("WEAPON_ABILITY_UP", M)] + proc("ADD_MATK_DOWN"), price)

        # ---- War Staff: a PHYSICAL staff. Winnehild's Battle Cry strikes with every
        # equipped weapon type using its Phys. Atk, and every other staff here is magic ----
        add(T, "weapon", tmpl_of["rod"][0], f"{pre} War Staff",
            {"ATK": W, "MATK": 0.4 * W, "ACC": acc, "CON": m1 * Ws},
            [("WEAPON_ABILITY_UP", M)] + proc("ADD_DEF_DOWN"), price)

        # ---- hexing weapons: high-chance status ailments (70+) -------------------
        if T >= 70:
            for hname, slot, ail in HEX_WEAPONS:
                tmpl, noun = tmpl_of[slot]
                main = "MATK" if slot == "rod" else "ATK"
                # shipped poison lasts 2 turns, the others 4-5
                turns = (2 if T < 90 else 3) if ail == "ADD_POISON_NORMAL" else PROC_TURNS[T]
                add(T, "weapon", tmpl, f"{pre} {hname} {noun}",
                    {main: 0.85 * W, "ACC": acc + m1 * Ws, "AGI": m2 * Ws},
                    [("WEAPON_ABILITY_UP", M)]
                    + proc(ail, chance=HEX_CHANCE[T], turns=turns),
                    price * 1.1)

        # ---- elemental weapons (70+); dual-element at 90+ ------------------------
        if T >= 70:
            E = ELEM_WEAPON_PCT[T]
            for el, up, _res, wslot in ELEMENTS:
                tmpl, noun = tmpl_of[wslot]
                add(T, "weapon", tmpl, f"{pre} {el} {noun}",
                    {"ATK": 0.85 * W, "MATK": (m1 + 0.2) * W, "ACC": acc,
                     "CON": m2 * Ws},
                    [("WEAPON_ABILITY_UP", M), (up, E)], price * 1.2)
                add(T, "weapon", tmpl_of["rod"][0], f"{pre} {el} Staff",
                    {"MATK": 0.9 * W, "MDEF": m1 * Ws, "ACC": acc,
                     "AGI": m2 * Ws},
                    [(up, E)], price * 1.2)
        if T >= 90:
            E = ELEM_WEAPON_PCT[T]
            for dname, e1, e2, wslot in DUAL_ELEMENT_WEAPONS:
                ups = [(f"{e1}_ABILITY_UP", E), (f"{e2}_ABILITY_UP", E)]
                tmpl, noun = tmpl_of[wslot]
                add(T, "weapon", tmpl, f"{pre} {dname} {noun}",
                    {"ATK": 0.8 * W, "MATK": (m1 + 0.25) * W, "ACC": acc},
                    [("WEAPON_ABILITY_UP", M)] + ups, price * 1.4)
                add(T, "weapon", tmpl_of["rod"][0], f"{pre} {dname} Staff",
                    {"MATK": 0.85 * W, "MDEF": m1 * Ws, "ACC": acc},
                    ups, price * 1.4)

        # ---- specialist weapon lines -------------------------------------------
        if T >= 80:
            for slot in ("dagger", "bow"):
                tmpl, noun = tmpl_of[slot]
                add(T, "weapon", tmpl, f"{pre} Gambler's {noun}",
                    {"ATK": 0.9 * W, "CON": (m1 + 0.2) * Ws, "AGI": m2 * Ws},
                    [("WEAPON_ABILITY_UP", M), ("HIT_OR_MISS", GAMBLE_CRIT[T])]
                   , price * 1.2)
            for slot in ("sword", "axe"):
                tmpl, noun = tmpl_of[slot]
                add(T, "weapon", tmpl, f"{pre} Headsman's {noun}",
                    {"ATK": W, "CON": m1 * Ws, "ACC": acc},
                    [("WEAPON_ABILITY_UP", M), ("INSTANT_DEATH", 0, 0, DEATH_CHANCE[T])]
                    + proc("ADD_DEF_DOWN", 0.6), price * 1.3)
        if T >= 90:
            for slot in ("sword", "lance", "dagger", "axe", "bow"):
                tmpl, noun = tmpl_of[slot]
                add(T, "weapon", tmpl, f"{pre} Twinfang {noun}",
                    {"ATK": 0.85 * W, "AGI": m1 * Ws, "ACC": acc + m2 * Ws},
                    [("WEAPON_ABILITY_UP", M), ("DOUBLE_HIT", 0)],
                    price * 1.5)
            for slot in ("axe", "lance"):
                tmpl, noun = tmpl_of[slot]
                add(T, "weapon", tmpl, f"{pre} Sundering {noun}",
                    {"ATK": W, "MATK": m1 * W, "ACC": acc},
                    [("WEAPON_ABILITY_UP", M)] + proc("ADD_DEF_DOWN", 0.6)
                    + proc("ADD_MDEF_DOWN", 0.6), price * 1.5)

        # ---- armour: three variants per slot, plus specialist pieces ------------
        for slot, tmpl, noun in ARMOUR_SLOTS:
            # weapons no longer carry SP (it does nothing there), so armour carries double
            spx = int(2 * sp * (1.5 if slot == "head" else 1.0))
            variants = [
                ("Heavy", {"DEF": 1.2 * D, "HP": H * (1 + m2), "MDEF": m1 * D, "MP": spx},
                 armour_regen),
                ("Warded", {"MDEF": 1.5 * D, "HP": 0.8 * H, "DEF": m1 * D,
                            "MATK": m2 * D, "MP": spx + (40 if T >= 70 else 30)},
                 caster_regen),
                ("Nimble", {"EVA": D, "HP": 0.6 * H, "AGI": 1.5 * m1 * D,
                            "ACC": m2 * D, "DEF": 0.4 * D, "MP": spx},
                 armour_regen),
            ]
            for vname, stats, extra in variants:
                add(T, "armour", tmpl, f"{pre} {vname} {noun}", stats, extra, price * 0.8)
        if T >= 70:
            add(T, "armour", ARMOUR_SLOTS[1][1], f"{pre} Clearmind Helm",
                {"MDEF": D, "HP": 0.7 * H, "AGI": m1 * D, "MP": int(1.5 * sp)},
                armour_regen, price * 0.9, immune=("Sleep", "Confusion", "Terror"))
            add(T, "armour", ARMOUR_SLOTS[2][1], f"{pre} Purity Mail",
                {"DEF": D, "MDEF": 0.6 * D, "HP": 0.8 * H, "MP": sp},
                armour_regen, price * 0.9, immune=("Poison", "Blindness", "Silence"))
        if T >= 80:
            # trades defence for offence; armour has no point budget, so the penalty is real
            add(T, "armour", ARMOUR_SLOTS[2][1], f"{pre} Berserker Mail",
                {"ATK": 1.5 * m1 * D, "CON": m1 * D, "HP": 1.5 * H,
                 "DEF": -0.4 * D, "MDEF": -0.6 * D, "MP": sp},
                armour_regen, price * 0.9)

        # ---- charms: stat combinations within 2.5 x danger -----------------------
        if T >= 80:
            shares = (0.50, 0.25, 0.15, 0.10)    # major, minor1, minor2, SP
        elif T >= 70:
            shares = (0.58, 0.32, 0.00, 0.10)
        else:
            shares = (0.65, 0.35, 0.00, 0.00)
        for cname, a, b, c in CHARMS:
            stats = {}
            for stat, share in ((a, shares[0]), (b, shares[1]), (c, shares[2]),
                                ("MP", shares[3])):
                if share:
                    stats[stat] = stats.get(stat, 0) + _from_points(stat, B * share)
            regen = caster_regen if a in ("MP", "MATK") else []
            add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} {cname}", stats, regen,
                price * 0.6)

        # ---- pendants, tokens and the lure: from tier 60 ------------------------
        for pname, ail, vals, major, minor in PASSIVES:
            stats = {major: _from_points(major, B * 0.40),
                     minor: _from_points(minor, B * 0.20)}
            if T >= 70 and major != "MP":
                stats["MP"] = _from_points("MP", B * 0.10)
            add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} {pname}", stats,
                [(ail, vals[T])], price * 1.1)
        add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Hunter's Lure",
            {"CON": _from_points("CON", B * 0.25), "ACC": _from_points("ACC", B * 0.15),
             "MP": _from_points("MP", B * 0.10) if T >= 70 else 0},
            [("ENCOUNT_UP", 2), ("EXPUP", PASSIVE_VALUES["EXPUP"][T]),
             ("JPUP", PASSIVE_VALUES["JPUP"][T])], price * 1.2)
        if T >= 80:
            add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Pendant of Vigor",
                {"HP": _from_points("HP", B * 0.30), "MP": _from_points("MP", B * 0.20)},
                [("ADD_HP_FIXED_REGENERATION",
                  int(PASSIVE_VALUES["ADD_HP_FIXED_REGENERATION"][T] * 0.6)),
                 ("ADD_MP_FIXED_REGENERATION",
                  int(PASSIVE_VALUES["ADD_MP_FIXED_REGENERATION"][T] * 0.6))],
                price * 1.3)

        # ---- relics: one permanent battle buff each (70+) -------------------------
        for rname, ail, val, frm, major, minor in (RELICS if RELICS_ENABLED else []):
            if T < frm:
                continue
            stats = {major: _from_points(major, B * 0.25),
                     minor: _from_points(minor, B * 0.15)}
            stats["MP"] = stats.get("MP", 0) + _from_points("MP", B * 0.10)
            add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} {rname}", stats,
                [(ail, val)], price * 2.0)

        # ---- talismans: status immunities ---------------------------------------
        for tname, imm, major, minor, frm in TALISMANS:
            if T < frm:
                continue
            stats = {major: _from_points(major, B * 0.35), minor: _from_points(minor, B * 0.20)}
            if T >= 70:
                stats["MP"] = stats.get("MP", 0) + _from_points("MP", B * 0.10)
            add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} {tname}", stats, [],
                price * (1.5 if len(imm) > 3 else 0.8), immune=imm)

        # ---- wards, sigils and elemental hearts ---------------------------------
        if T >= 70:
            for el, up, res, _w in ELEMENTS:
                add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Ward of {el}",
                    {"MDEF": _from_points("MDEF", B * 0.40), "HP": _from_points("HP", B * 0.25),
                     "MP": _from_points("MP", B * 0.10)},
                    [(res, WARD_RESIST[T])], price * 0.7)
                add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Sigil of {el}",
                    {"MATK": _from_points("MATK", B * 0.40), "MP": _from_points("MP", B * 0.20),
                     "ACC": _from_points("ACC", B * 0.15)},
                    [(up, SIGIL_PCT[T])], price * 0.9)
        if T >= 90:
            res_of = {el: res for el, _u, res, _w in ELEMENTS}
            for e1, e2 in DUAL_WARDS:
                add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Ward of {e1} and {e2}",
                    {"MDEF": _from_points("MDEF", B * 0.35), "DEF": _from_points("DEF", B * 0.20),
                     "MP": _from_points("MP", B * 0.10)},
                    [(res_of[e1], WARD_RESIST[T]), (res_of[e2], WARD_RESIST[T])],
                    price * 0.9)
            for el, up, res, _w in ELEMENTS:
                add(T, "accessory", ACCESSORY_TEMPLATE, f"{pre} Heart of {el}",
                    {"MATK": _from_points("MATK", B * 0.30), "MDEF": _from_points("MDEF", B * 0.20),
                     "MP": _from_points("MP", B * 0.10)},
                    [(up, SIGIL_PCT[T]), (res, WARD_RESIST[T])], price * 1.2)

    # consumables: percentage HP heals - the shipped fixed 500-1,750 HP heals are nothing
    # against 15-35k HP pools. Cloned from Revitalizing Jam (one ally) and the Healing
    # Grape bunch (whole party).
    out.append(dict(tier=60, kind="consumable", template=VITAL_SINGLE_TEMPLATE,
                    name="Vital Draught", stats={}, immune=(),
                    ailment=[("HP_RATIO_RECOVERY", VITAL_SINGLE_PCT)], price=VITAL_SINGLE_PRICE,
                    desc=f"Restores {VITAL_SINGLE_PCT}% of max HP to one ally."))
    out.append(dict(tier=60, kind="consumable", template=VITAL_GROUP_TEMPLATE,
                    name="Vital Cask", stats={}, immune=(),
                    ailment=[("HP_RATIO_RECOVERY", VITAL_GROUP_PCT)], price=VITAL_GROUP_PRICE,
                    desc=f"Restores {VITAL_GROUP_PCT}% of max HP to the entire party."))
    # consumables: a far stronger SP restore, single target and whole party
    out.append(dict(tier=60, kind="consumable", template=SP_SINGLE_TEMPLATE,
                    name="Invigorating Draught", stats={}, immune=(),
                    ailment=[("MP_FIXED_RECOVERY", SP_SINGLE_AMOUNT)], price=SP_SINGLE_PRICE,
                    desc=f"Restores {SP_SINGLE_AMOUNT} SP to one ally."))
    out.append(dict(tier=60, kind="consumable", template=SP_GROUP_TEMPLATE,
                    name="Invigorating Cask", stats={}, immune=(),
                    ailment=[("MP_FIXED_RECOVERY", SP_GROUP_AMOUNT)], price=SP_GROUP_PRICE,
                    desc=f"Restores {SP_GROUP_AMOUNT} SP to the entire party."))
    for el, template in SOULSTONE_XL:
        word = {"Thunder": "lightning", "Shadow": "dark"}.get(el, el.lower())
        out.append(dict(tier=SOULSTONE_XL_TIER, kind="consumable", gated=True,
                        template=template, name=f"{el} Soulstone (XL)", stats={}, immune=(),
                        ailment=[("HP_FIXED_DAMAGE", SOULSTONE_XL_DAMAGE)],
                        price=SOULSTONE_XL_PRICE,
                        desc=f"Deals {SOULSTONE_XL_DAMAGE:,} {word} damage to all foes."))
    return out
