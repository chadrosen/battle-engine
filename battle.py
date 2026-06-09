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
            'weapon': cls['weapon']
        }

    unit1 = make_unit(char1_name)
    unit2 = make_unit(char2_name)

    rng = random.Random(seed)

    # Determine turn order — fastest first, ties broken by rng
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

            hit_roll = rng.randint(1, 20)
            hits = (hit_roll + attacker['attack']) >= defender['defense']

            speed_advantage = defender['speed'] - attacker['speed']
            dodge_chance = max(0.0, min(0.5, speed_advantage / 30))
            dodged = hits and rng.random() < dodge_chance

            if hits and not dodged:
                damage_die = weapons[attacker['weapon']]['damage_die']
                damage = rng.randint(1, damage_die)
                defender['hp'] = max(0, defender['hp'] - damage)
                result_text = (
                    f"{attacker['name']} hits {defender['name']} for {damage} damage "
                    f"(roll: {hit_roll}). {defender['name']} has {defender['hp']} HP remaining."
                )
            elif dodged:
                damage = 0
                result_text = f"{defender['name']} dodges {attacker['name']}'s attack (roll: {hit_roll})."
            else:
                damage = 0
                result_text = f"{attacker['name']} misses {defender['name']} (roll: {hit_roll})."

            turns.append({
                'turn_id': turn_id,
                'attacker': attacker['name'],
                'defender': defender['name'],
                'hit_roll': hit_roll,
                'hit': hits and not dodged,
                'dodged': dodged,
                'damage': damage,
                'defender_hp': defender['hp'],
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
        'turns': turns
    }


def main():
    parser = argparse.ArgumentParser(description='Run a 1v1 battle between two characters.')
    parser.add_argument('character1', help='Name of the first character')
    parser.add_argument('character2', help='Name of the second character')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    parser.add_argument('--output', default='/app/result.json', help='Output file path')
    args = parser.parse_args()

    try:
        result = run_battle(args.character1, args.character2, args.seed)
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=4)
        print(json.dumps(result, indent=4))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
