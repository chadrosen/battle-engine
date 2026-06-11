import json
import random
import argparse
import sys
import os

CHARACTERS_FILE = os.path.join(os.path.dirname(__file__), 'characters.json')
CLASSES_FILE = os.path.join(os.path.dirname(__file__), 'classes.json')
WEAPONS_FILE = os.path.join(os.path.dirname(__file__), 'weapons.json')


def load_data():
    with open(CHARACTERS_FILE) as f:
        characters = json.load(f)
    with open(CLASSES_FILE) as f:
        classes = json.load(f)
    with open(WEAPONS_FILE) as f:
        weapons = json.load(f)
    return characters, classes, weapons


def get_death_cause(result):
    loser_hp = {k: v for k, v in result['final_hp'].items() if v == 0}
    if not loser_hp:
        return 'basic_attack'
    loser_name = list(loser_hp.keys())[0]
    for t in reversed(result['turns']):
        if t.get('action') == 'burn_tick' and t.get('attacker') == loser_name and t.get('attacker_hp', 1) == 0:
            return 'burn'
        if t.get('defender') == loser_name and t.get('critical') and t.get('hit') and t.get('defender_hp', 1) == 0:
            return 'critical_hit'
        if t.get('attacker') == loser_name and t.get('critical') and not t.get('hit') and t.get('attacker_hp', 1) == 0:
            return 'critical_miss'
        if t.get('defender') == loser_name and not t.get('critical') and t.get('hit') and t.get('defender_hp', 1) == 0:
            return 'basic_attack'
        if t.get('action') == 'spell' and t.get('defender') == loser_name and t.get('defender_hp', 1) == 0:
            return 'basic_attack'
    return 'basic_attack'


def run_battle(char1_name, char2_name, seed):
    characters, classes, weapons = load_data()

    if char1_name not in characters:
        raise ValueError(f"Unknown character: {char1_name}")
    if char2_name not in characters:
        raise ValueError(f"Unknown character: {char2_name}")

    def make_unit(name):
        char = characters[name]
        cls = classes[char['class']]
        prog = cls['progression']
        level = char.get('level', 1)
        gains = level - 1
        hp = cls['base_hp'] + round(gains * prog['hp_per_level'])
        attack = cls['attack'] + round(gains * prog['attack_per_level'])
        defense = cls['defense'] + round(gains * prog['defense_per_level'])
        speed = cls['speed'] + round(gains * prog['speed_per_level'])
        return {
            'name': name,
            'class': char['class'],
            'level': level,
            'hp': hp,
            'max_hp': hp,
            'attack': attack,
            'defense': defense,
            'speed': speed,
            'weapon': cls['weapon'],
            'stun_turns': 0,
            'burn_turns': 0,
            'spell_action_count': 0,
        }

    unit1 = make_unit(char1_name)
    unit2 = make_unit(char2_name)
    rng = random.Random(seed)

    stats = {
        unit1['name']: {'damage_dealt': 0, 'crit_hits': 0, 'crit_misses': 0, 'attacks_dodged': 0},
        unit2['name']: {'damage_dealt': 0, 'crit_hits': 0, 'crit_misses': 0, 'attacks_dodged': 0},
    }

    if unit1['speed'] > unit2['speed']:
        turn_order = [unit1, unit2]
    elif unit2['speed'] > unit1['speed']:
        turn_order = [unit2, unit1]
    else:
        turn_order = [unit1, unit2] if rng.random() < 0.5 else [unit2, unit1]

    turns = []
    turn_id = 1
    winner = None

    while unit1['hp'] > 0 and unit2['hp'] > 0:
        for attacker in turn_order:
            defender = unit2 if attacker is unit1 else unit1

            if defender['hp'] <= 0:
                break

            # Apply burn damage at start of burning unit's turn
            if attacker['burn_turns'] > 0:
                attacker['hp'] = max(0, attacker['hp'] - 2)
                attacker['burn_turns'] -= 1
                turns.append({
                    'turn_id': turn_id,
                    'attacker': attacker['name'],
                    'action': 'burn_tick',
                    'burn_damage': 2,
                    'burn_turns_remaining': attacker['burn_turns'],
                    'attacker_hp': attacker['hp'],
                    'defender_hp': defender['hp'],
                    'attacker_status': 'burning' if attacker['burn_turns'] > 0 else 'none',
                    'defender_status': 'stunned' if defender['stun_turns'] > 0 else 'none',
                    'result': f"{attacker['name']} takes 2 burn damage. {attacker['burn_turns']} burn turns remaining."
                })
                turn_id += 1
                if attacker['hp'] <= 0:
                    winner = defender['name']
                    break

            if winner:
                break

            # Stunned unit skips turn
            if attacker['stun_turns'] > 0:
                attacker['stun_turns'] -= 1
                turns.append({
                    'turn_id': turn_id,
                    'attacker': attacker['name'],
                    'action': 'none',
                    'stun_turns_remaining': attacker['stun_turns'],
                    'damage': 0,
                    'attacker_hp': attacker['hp'],
                    'defender_hp': defender['hp'],
                    'attacker_status': 'stunned',
                    'defender_status': 'stunned' if defender['stun_turns'] > 0 else 'none',
                    'result': f"{attacker['name']} is stunned and cannot act!"
                })
                turn_id += 1
                continue

            hit_roll = rng.randint(1, 20)

            # Mage spell casting: every 4th action turn
            if attacker['class'] == 'mage':
                attacker['spell_action_count'] += 1
                if attacker['spell_action_count'] % 4 == 0:
                    # Fireball spell
                    fireball_damage = rng.randint(1, 8) + attacker['level']
                    defender['hp'] = max(0, defender['hp'] - fireball_damage)
                    defender['burn_turns'] = 3
                    stats[attacker['name']]['damage_dealt'] += fireball_damage
                    turns.append({
                        'turn_id': turn_id,
                        'attacker': attacker['name'],
                        'defender': defender['name'],
                        'action': 'spell',
                        'action_type': 'fireball',
                        'hit_roll': hit_roll,
                        'hit': True,
                        'dodged': False,
                        'damage': fireball_damage,
                        'attacker_hp': attacker['hp'],
                        'defender_hp': defender['hp'],
                        'critical': False,
                        'attacker_status': 'none',
                        'defender_status': 'none',
                        'burn_turns_remaining': 3,
                        'result': f"{attacker['name']} casts fireball at {defender['name']} for {fireball_damage} damage. {defender['name']} burns for 3 turns."
                    })
                    turn_id += 1
                    if defender['hp'] <= 0:
                        winner = attacker['name']
                        break
                    continue

            # Critical miss
            if hit_roll <= 2:
                attacker['hp'] = max(0, attacker['hp'] - 2)
                attacker['stun_turns'] += 1
                stats[attacker['name']]['crit_misses'] += 1
                turns.append({
                    'turn_id': turn_id,
                    'attacker': attacker['name'],
                    'defender': defender['name'],
                    'action': 'attack',
                    'hit_roll': hit_roll,
                    'hit': False,
                    'dodged': False,
                    'damage': 0,
                    'attacker_status': 'stunned',
                    'defender_status': 'stunned' if defender['stun_turns'] > 0 else 'none',
                    'defender_hp': defender['hp'],
                    'attacker_hp': attacker['hp'],
                    'critical': True,
                    'result': f"{attacker['name']} rolls a critical miss, takes 2 damage, and is stunned!"
                })
                turn_id += 1
                if attacker['hp'] <= 0:
                    winner = defender['name']
                    break
                continue

            # Critical hit
            if hit_roll >= 18:
                damage_die = weapons[attacker['weapon']]['damage_die']
                damage = round(rng.randint(1, damage_die) * 1.5)
                defender['hp'] = max(0, defender['hp'] - damage)
                defender['stun_turns'] += 1
                stats[attacker['name']]['crit_hits'] += 1
                stats[attacker['name']]['damage_dealt'] += damage
                turns.append({
                    'turn_id': turn_id,
                    'attacker': attacker['name'],
                    'defender': defender['name'],
                    'action': 'attack',
                    'hit_roll': hit_roll,
                    'hit': True,
                    'dodged': False,
                    'damage': damage,
                    'attacker_hp': attacker['hp'],
                    'defender_hp': defender['hp'],
                    'critical': True,
                    'attacker_status': 'stunned' if attacker['stun_turns'] > 0 else 'none',
                    'defender_status': 'stunned',
                    'result': f"{attacker['name']} rolls a critical hit. {defender['name']} takes extra damage and is stunned!"
                })
                turn_id += 1
                if defender['hp'] <= 0:
                    winner = attacker['name']
                    break
                continue

            # Normal attack
            hits = (hit_roll + attacker['attack']) >= defender['defense']
            spd = defender['speed'] - attacker['speed']
            dodge_chance = max(0.0, min(0.35, spd / 40))
            dodged = hits and rng.random() < dodge_chance

            if hits and not dodged:
                damage_die = weapons[attacker['weapon']]['damage_die']
                damage = rng.randint(1, damage_die)
                defender['hp'] = max(0, defender['hp'] - damage)
                stats[attacker['name']]['damage_dealt'] += damage
                result_text = (
                    f"{attacker['name']} hits {defender['name']} for {damage} damage "
                    f"(roll: {hit_roll}). {defender['name']} has {defender['hp']} HP remaining."
                )
            elif dodged:
                damage = 0
                stats[attacker['name']]['attacks_dodged'] += 1
                result_text = f"{defender['name']} dodges {attacker['name']}'s attack (roll: {hit_roll})."
            else:
                damage = 0
                result_text = f"{attacker['name']} misses {defender['name']} (roll: {hit_roll})."

            turns.append({
                'turn_id': turn_id,
                'attacker': attacker['name'],
                'defender': defender['name'],
                'action': 'attack',
                'hit_roll': hit_roll,
                'hit': hits and not dodged,
                'dodged': dodged,
                'damage': damage,
                'attacker_hp': attacker['hp'],
                'defender_hp': defender['hp'],
                'critical': False,
                'attacker_status': 'stunned' if attacker['stun_turns'] > 0 else 'none',
                'defender_status': 'stunned' if defender['stun_turns'] > 0 else 'none',
                'result': result_text
            })
            turn_id += 1

            if defender['hp'] <= 0:
                winner = attacker['name']
                break

        if winner:
            break

    return {
        'winner': winner,
        'seed': seed,
        'final_hp': {
            unit1['name']: unit1['hp'],
            unit2['name']: unit2['hp']
        },
        'turns': turns,
        'stats': stats
    }


def run_simulation(char1_name, char2_name, start_seed, count, verbose=False):
    wins = {char1_name: 0, char2_name: 0}
    turns_list = []
    death_causes = {'basic_attack': 0, 'critical_hit': 0, 'critical_miss': 0, 'burn': 0}
    all_turns = []

    for i in range(count):
        seed = start_seed + i
        result = run_battle(char1_name, char2_name, seed)
        winner = result['winner']
        if winner:
            wins[winner] = wins.get(winner, 0) + 1
        turns_list.append(len(result['turns']))
        cause = get_death_cause(result)
        death_causes[cause] = death_causes.get(cause, 0) + 1
        if verbose:
            all_turns.extend(result['turns'])

    total = count
    output = {
        'fighters': [char1_name, char2_name],
        'seed_range': [start_seed, start_seed + count - 1],
        'total_simulations': total,
        'wins': wins,
        'win_percentage': {k: round(v / total * 100, 2) for k, v in wins.items()},
        'average_turns': round(sum(turns_list) / len(turns_list), 2),
        'minimum_turns': min(turns_list),
        'maximum_turns': max(turns_list),
        'death_causes': death_causes
    }
    if verbose:
        output['turns'] = all_turns
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('character1')
    parser.add_argument('character2')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', default='/app/result.json')
    parser.add_argument('--simulate', action='store_true')
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--start-seed', type=int, default=1)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    try:
        if args.simulate:
            result = run_simulation(args.character1, args.character2, args.start_seed, args.count, verbose=args.verbose)
            output = json.dumps(result, indent=4)
            print(output)
            with open(args.output, 'w') as f:
                f.write(output)
        else:
            result = run_battle(args.character1, args.character2, args.seed)
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=4)
            print(json.dumps(result, indent=4))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()