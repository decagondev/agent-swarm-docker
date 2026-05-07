import os
import time
import glob
from datetime import datetime
import sys

DATA_INPUT = "/app/data/input"
DATA_RESULTS = "/app/data/results"
DATA_OUTPUT = "/app/data/output"

os.makedirs(DATA_INPUT, exist_ok=True)
os.makedirs(DATA_RESULTS, exist_ok=True)
os.makedirs(DATA_OUTPUT, exist_ok=True)

def main():
    if len(sys.argv) < 2:
        paragraph = "The quick brown fox jumps over the lazy dog. This is a test paragraph for the agent swarm."
        print("⚠️  No paragraph provided — using demo text.")
    else:
        paragraph = " ".join(sys.argv[1:])

    # Step 1: Supervisor creates the initial file(s)
    input_file = f"{DATA_INPUT}/initial_paragraph.txt"
    with open(input_file, "w", encoding="utf-8") as f:
        f.write(paragraph)
    print(f"📝 Orchestrator created initial file: {input_file}")

    # Optional batch mode: generate 20 files (uncomment or run separately)
    # for i in range(20):
    #     with open(f"{DATA_INPUT}/file_{i+1:02d}.txt", "w") as f:
    #         f.write(f"Batch file {i+1}: " + paragraph)

    print("⏳ Waiting for sub-agents to hand off results... (they process every .txt in input/)")

    # Step 2: Poll until we have all 4 expected result types per input file
    expected_tasks = ["capitalize", "reverse", "count_consonants", "vowel_random"]
    start = time.time()
    while True:
        result_files = glob.glob(f"{DATA_RESULTS}/*.result")
        if len(result_files) >= len(expected_tasks) * len(glob.glob(f"{DATA_INPUT}/*.txt")):
            break
        if time.time() - start > 60:  # safety timeout
            print("⚠️ Timeout waiting for workers.")
            break
        time.sleep(2)

    # Step 3: Orchestrator collects everything and writes final report + log
    timestamp = datetime.now().isoformat()
    log_file = f"{DATA_OUTPUT}/orchestrator_log.txt"
    report_file = f"{DATA_OUTPUT}/final_report.txt"

    with open(report_file, "w", encoding="utf-8") as report:
        report.write(f"FINAL REPORT — Generated at {timestamp}\n")
        report.write(f"Input files processed: {len(glob.glob(f'{DATA_INPUT}/*.txt'))}\n\n")

        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"[{timestamp}] Orchestrator started collection\n")

            for res_file in sorted(glob.glob(f"{DATA_RESULTS}/*.result")):
                with open(res_file, "r", encoding="utf-8") as f:
                    content = f.read()
                report.write(f"--- {os.path.basename(res_file)} ---\n{content}\n\n")
                log.write(f"[{datetime.now().isoformat()}] Collected result from {os.path.basename(res_file)}\n")

    print(f"✅ Orchestrator finished!")
    print(f"📁 Final report  → shared-data/output/final_report.txt")
    print(f"📋 Master log    → shared-data/output/orchestrator_log.txt")
    print(f"📂 All raw results → shared-data/results/")

if __name__ == "__main__":
    main()
