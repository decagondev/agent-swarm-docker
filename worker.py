import os
import glob
import argparse
from datetime import datetime
import random
import string

AGENT_ID = os.uname().nodename
DATA_INPUT = "/app/data/input"
DATA_RESULTS = "/app/data/results"

os.makedirs(DATA_RESULTS, exist_ok=True)

def count_consonants(text):
    vowels = set("aeiouAEIOU")
    return sum(1 for c in text if c.isalpha() and c not in vowels)

def count_vowels(text):
    vowels = set("aeiouAEIOU")
    return sum(1 for c in text if c.isalpha() and c in vowels)

parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True, choices=["capitalize", "reverse", "count_consonants", "vowel_random"])
args = parser.parse_args()

print(f"🚀 {args.task.upper()} Agent {AGENT_ID} starting...")

for txt_file in glob.glob(f"{DATA_INPUT}/*.txt"):
    filename = os.path.basename(txt_file)
    with open(txt_file, "r", encoding="utf-8") as f:
        content = f.read()

    timestamp = datetime.now().isoformat()
    result_file = f"{DATA_RESULTS}/{args.task}_{filename}.result"

    if args.task == "capitalize":
        result = content.upper()
        report = f"Agent {AGENT_ID} | {timestamp} | CAPITALIZED → {len(result)} chars\n---\n{result}\n"

    elif args.task == "reverse":
        result = content[::-1]
        report = f"Agent {AGENT_ID} | {timestamp} | REVERSED → {len(result)} chars\n---\n{result}\n"
        # Also save pure reversed file as requested
        with open(f"{DATA_RESULTS}/reversed_{filename}", "w", encoding="utf-8") as rf:
            rf.write(result)

    elif args.task == "count_consonants":
        count = count_consonants(content)
        report = f"Agent {AGENT_ID} | {timestamp} | CONSONANTS = {count}\n"

    elif args.task == "vowel_random":
        vowel_count = count_vowels(content)
        num_chars = vowel_count * 2
        random_str = "".join(random.choices(string.ascii_letters + string.digits, k=num_chars))
        report = f"Agent {AGENT_ID} | {timestamp} | VOWELS = {vowel_count} → {num_chars} random chars generated\nRandom file: random_{filename}\n"
        with open(f"{DATA_RESULTS}/random_{filename}", "w", encoding="utf-8") as rf:
            rf.write(random_str)

    with open(result_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ {args.task} Agent {AGENT_ID} handed off result for {filename}")

print(f"✅ {args.task.upper()} Agent {AGENT_ID} finished.")
